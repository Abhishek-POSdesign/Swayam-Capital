"""
Pydantic API request and response data models for Swayam Capital.

Enforces strict input validation, type coercion, and serializable schemas for
FastAPI REST endpoints and WebSocket communication.
"""

from datetime import date
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class LegRequest(BaseModel):
    """Specification of an individual option leg in an API request."""
    strike: float = Field(..., description="Strike price in rupees")
    option_type: str = Field(..., description="CE or PE")
    direction: str = Field(..., description="buy or sell")
    quantity_lots: int = Field(default=1, ge=1, description="Quantity in lots")
    entry_premium: float = Field(default=0.0, ge=0.0, description="Option premium per share (limit price for a LIMIT leg; the fill for paper)")
    expiry_date: str = Field(..., description="Expiration date in YYYY-MM-DD format")
    lot_size: Optional[int] = Field(
        default=None,
        ge=1,
        description=(
            "Contract size. IGNORED if supplied. The server reads it from the "
            "FYERS contract master, because a browser that hardcodes 75 is how "
            "every contract-scaled figure came to be 15.4% too large."
        ),
    )
    order_type: str = Field(
        default="MARKET",
        description=(
            "Per-leg order type, MARKET or LIMIT, chosen on the execution ticket. "
            "MARKET fills at the server's live quote at the moment of sending. "
            "LIMIT fills at limit_price only if the market is at or through it; "
            "otherwise nothing fills and the answer says where the market is."
        ),
    )
    limit_price: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="His price for a LIMIT leg. Ignored for MARKET. Falls back to entry_premium when absent.",
    )

    @field_validator("option_type")
    @classmethod
    def validate_option_type(cls, v: str) -> str:
        norm = v.upper()
        if norm not in ("CE", "PE", "CALL", "PUT"):
            raise ValueError(f"Invalid option_type: {v}. Must be CE or PE.")
        return "CE" if norm in ("CE", "CALL") else "PE"

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, v: str) -> str:
        norm = v.lower()
        if norm not in ("buy", "sell"):
            raise ValueError(f"Invalid direction: {v}. Must be 'buy' or 'sell'.")
        return norm


class StrategyComputeRequest(BaseModel):
    """Payload for computing payoff curves and Greeks."""
    strategy_name: str = Field(..., description="Name of strategy preset or custom spread")
    underlying: str = Field(default="NIFTY", description="Underlying asset symbol")
    legs: list[LegRequest] = Field(..., min_length=1, description="List of option legs")
    current_spot: float = Field(..., gt=0.0, description="Current underlying spot price")
    iv_per_leg: dict[str, float] = Field(
        default_factory=dict,
        description="Mapping of leg key (e.g. '24850_PE') to implied volatility decimal (e.g. 0.15)",
    )
    target_date: Optional[str] = Field(
        default=None,
        description="Optional valuation date YYYY-MM-DD for T+N payoff evaluation (must not exceed expiry)",
    )
    planned_exit_date: Optional[str] = Field(
        default=None,
        description=(
            "When Abhishek intends to be out, YYYY-MM-DD. Today or absent means an "
            "intraday trade, which nothing blocks. A later date means the position "
            "will be carried overnight, and the carry rules then apply: it must be "
            "hedged, and a gap of twice the average daily move must cost no more "
            "than 2% of live capital."
        ),
    )
    target_spot: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Optional 'what-if' spot for the NIFTY-target slider; returns projected P&L at this spot on target_date",
    )
    iv_shift_pct: float = Field(
        default=0.0,
        description="Optional IV percentage shift [-90, +200] for stress-testing payoff curve",
    )


class ExecuteRequest(StrategyComputeRequest):
    """Payload for executing a trade (paper or real)."""
    mode: str = Field(default="paper", description="Execution mode: 'paper' or 'real'")
    order_type: str = Field(default="LIMIT", description="Order type: 'LIMIT' or 'MARKET'")
    session_id: Optional[str] = Field(default=None, description="Active AI session ID to link to trade")
    leg_order: str = Field(
        default="buys_first",
        description=(
            "buys_first: the server re-orders the legs so every buy fills before "
            "any sell, which earns the hedged margin. as_sent: the legs fill in "
            "exactly the order given, which is the order he chose on the ticket."
        ),
    )
    execution_mode: str = Field(
        default="all",
        description="all: every leg in one send. one_by_one: this request opens the trade with its first leg; later legs are added with POST /api/positions/{id}/legs.",
    )
    idempotency_key: Optional[str] = Field(
        default=None,
        max_length=100,
        description=(
            "A key the browser generates once per execution ticket, keeps in local "
            "storage, and reuses on every retry until it gets a final answer. The "
            "same key with the same trade replays the first response instead of "
            "opening a second position. The same key with a DIFFERENT trade is "
            "rejected with 409. Omit it and there is no double-click protection."
        ),
    )


class PreviewLegItem(BaseModel):
    """Individual leg specification for pre-execution sequence preview."""
    strike: float = Field(..., description="Strike price in rupees")
    option_type: str = Field(..., description="CE or PE")
    direction: str = Field(..., description="buy or sell")
    quantity_lots: int = Field(default=1, ge=1, description="Quantity in lots")
    entry_premium: float = Field(default=0.0, ge=0.0, description="Option premium per share")
    expiry_date: str = Field(..., description="Expiration date YYYY-MM-DD")
    lot_size: Optional[int] = Field(
        default=None,
        ge=1,
        description="Contract size. IGNORED if supplied; resolved server-side.",
    )
    order_type: str = Field(default="LIMIT", description="LIMIT or MARKET")


class AddLegRequest(BaseModel):
    """One leg added to a trade that is already open.

    "Execute one by one" opens the trade with its first leg and adds each later
    leg here, so the trade keeps one identity while its shape changes. That is
    the campaign model from docs/PLAN.md 2.11, in his words: legs are added and
    squared off inside the trade, and it closes when every leg is closed or
    when he says so.
    """
    leg: LegRequest
    current_spot: float = Field(..., gt=0.0, description="Spot the browser had; the server records its own where it can")
    idempotency_key: Optional[str] = Field(default=None, max_length=100)


class MultiLegPreviewRequest(BaseModel):
    """Request payload to simulate and order legs for margin safety."""
    underlying: str = Field(default="NIFTY", description="Underlying symbol")
    current_spot: float = Field(..., gt=0.0, description="Current spot price")
    legs: list[PreviewLegItem] = Field(..., min_length=1, description="Strategy legs to order")
    leg_order: str = Field(
        default="buys_first",
        description="buys_first re-orders so every buy precedes every sell; as_sent keeps the order given, which is his order on the ticket.",
    )


class OrderedLegStep(BaseModel):
    """Step in margin-safe execution order."""
    sequence: int
    strike: float
    option_type: str
    direction: str
    quantity_lots: int
    lot_size: int
    entry_premium: float
    order_type: str
    estimated_margin_inr: Optional[float] = Field(
        default=None,
        description=(
            "Always null. The broker prices a basket, not a leg, so a per-leg "
            "margin is not a real number. It used to be a hardcoded constant."
        ),
    )
    entry_charges_inr: Optional[float] = Field(
        default=None,
        description="What buying or selling this leg costs, from the versioned charge schedule. Null if the schedule cannot be read.",
    )
    action_note: str


class MultiLegPreviewResponse(BaseModel):
    """Legs sorted BUY first, with the broker's real margin for the basket.

    Every margin figure is Optional and every one of them may be null. That is
    deliberate. These used to be hardcoded constants of Rs 32,000 hedged and
    Rs 1,15,000 naked, which understated the real requirement by roughly half.
    They now come from the FYERS margin endpoint, and when FYERS cannot be
    reached the answer is null with a reason, never an estimate.
    """
    ordered_legs: list[OrderedLegStep]
    buy_count: int
    sell_count: int
    total_debit_credit_inr: float
    entry_charges_total_inr: Optional[float] = Field(
        default=None, description="The legs' entry charges summed. Null if any leg could not be charged."
    )

    margin_required_inr: Optional[float] = Field(
        default=None, description="Broker margin for the basket as ordered. Null means unavailable."
    )
    margin_if_unhedged_inr: Optional[float] = Field(
        default=None, description="Broker margin for the short legs alone, for comparison."
    )
    margin_saved_by_hedge_inr: Optional[float] = Field(
        default=None, description="Difference between the two above. Null if either is unavailable."
    )
    margin_available_inr: Optional[float] = Field(
        default=None, description="Broker's available margin at the time of the quote."
    )
    margin_source: Optional[str] = Field(default=None, description="Where the margin figure came from.")
    margin_fetched_at: Optional[str] = Field(default=None, description="When the margin was quoted.")
    margin_unavailable_reason: Optional[str] = Field(
        default=None, description="Why margin could not be established. Show this instead of a number."
    )


class ValidationCheck(BaseModel):
    """Result of a single Method rule check."""
    rule: str
    verdict: str  # "PASS" or "FAIL"
    actual: Optional[float] = None
    actual_inr: Optional[float] = None
    cap_inr: Optional[float] = None
    floor: Optional[float] = None
    tolerance_pct: Optional[float] = None
    note: Optional[str] = None
    blocking: bool = Field(
        default=True,
        description="False for checks that inform but never stop a trade.",
    )


class RiskVerdict(BaseModel):
    """Verdict and metrics for a risk cap evaluation.

    pct_of_margin is a PERCENTAGE already, e.g. 0.62 means 0.62%. The frontend
    multiplied it by 100 again and printed 62% where the truth was 0.62%.
    Do not multiply it. It is named badly for history's sake; the field to
    trust when displaying is `arithmetic`.
    """
    loss_inr: Optional[float]
    cap_inr: float
    pct_of_margin: Optional[float]
    passed: bool
    cost_reserve_inr: Optional[float] = Field(
        default=None,
        description="Round-trip cost reserved and included in loss_inr. Null when not applicable.",
    )
    arithmetic: Optional[str] = Field(
        default=None,
        description="The whole sum in words, e.g. 'price loss + costs = total vs cap'. Display this.",
    )


class CapitalContext(BaseModel):
    """The account figures the caps were computed from, with provenance."""
    risk_capital_inr: float
    free_cash_inr: float
    collateral_inr: float
    cash_equivalent_pledged_inr: Optional[float] = None
    cash_equivalent_as_of: Optional[str] = None
    deployable_margin_ceiling_inr: Optional[float] = None
    ceiling_unavailable_reason: Optional[str] = None
    reconciliation_note: Optional[str] = None
    primary_risk_cap_inr: float
    black_swan_fuse_inr: float
    source: str
    taken_at: str


class ValidationResponse(BaseModel):
    """Complete rule compliance audit for an options spread."""
    passed: bool
    overall_passed: bool
    realistic_risk: RiskVerdict
    blast_radius: RiskVerdict
    checks: list[ValidationCheck]
    warnings: list[str] = []
    capital: Optional[CapitalContext] = None
    execution_blocked_reason: Optional[str] = Field(
        default=None,
        description="Set when the structure may be viewed but must not be executed.",
    )
    max_loss_is_unlimited: bool = Field(
        default=False,
        description=(
            "True when the loss at expiry has no ceiling, which happens with a net "
            "short call position. Display 'Unlimited', never a number. JSON cannot "
            "carry infinity, so blast_radius.loss_inr is null in that case."
        ),
    )
    intraday: bool = Field(
        default=True,
        description="True when this is a same-day trade. Nothing blocks an intraday entry.",
    )
    carry: Optional[dict] = Field(
        default=None,
        description="The overnight carry assessment: gap loss, cap, move profile and reasons.",
    )
    running_loss_threshold_inr: Optional[float] = Field(
        default=None,
        description="1% of live capital. Above this on a live position the app goes red.",
    )


class PayoffPointResponse(BaseModel):
    """Single coordinate on the payoff curve."""
    spot: float
    pnl_expiry: float
    pnl_today: float
    pnl: Optional[float] = None


class PayoffCurveResponse(BaseModel):
    """Full payoff curve analysis."""
    spot_range: list[float]
    points: list[PayoffPointResponse]
    breakevens: list[float]
    max_profit_inr: float
    max_loss_inr: float
    rr_implied: float
    net_debit_credit_inr: float


class LegGreeksItem(BaseModel):
    """Individual option leg Greek metrics.

    iv is the volatility IMPLIED FROM THE LEG'S PRICE (real LTP or user-entered limit),
    never a placeholder. iv_available is False when it could not be solved from a price —
    in which case the UI must show '—', not a fake number.
    """
    strike: float
    option_type: str
    direction: str
    delta: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    gamma: Optional[float] = None
    iv: Optional[float] = None
    iv_available: bool = True


class GreeksResponse(BaseModel):
    """Standardized aggregated portfolio Greeks."""
    net_delta: float
    net_gamma: float
    net_theta_per_day: float
    net_vega: float
    net_rho: float
    pop: Optional[float] = Field(default=None, description="Probability of Profit percentage (0-100)")
    per_leg: list[LegGreeksItem] = Field(default_factory=list, description="Per-leg calculated Greeks")


class StrategyComputeResponse(BaseModel):
    """Combined strategy computation output."""
    payoff_curve: PayoffCurveResponse
    payoff_curve_expiry: Optional[PayoffCurveResponse] = None
    payoff_curve_target: Optional[PayoffCurveResponse] = None
    greeks: GreeksResponse
    pop: Optional[float] = Field(default=None, description="Top-level Probability of Profit percentage")
    per_leg: list[LegGreeksItem] = Field(default_factory=list, description="Per-leg calculated Greeks")
    projected_pnl_target_inr: Optional[float] = Field(
        default=None,
        description="P&L (₹) at target_spot on target_date, for the NIFTY-target slider readout. Null if target_spot not given.",
    )
    projected_pnl_target_pct: Optional[float] = Field(
        default=None,
        description="Projected P&L as % of net debit/credit, for the slider readout.",
    )
    target_spot_used: Optional[float] = Field(
        default=None, description="Echo of the target_spot the projection was computed at."
    )


class StrikeQuote(BaseModel):
    """Quote for an option contract. Null fields mean 'not available' — never faked.

    Everything FYERS sends per contract is carried, nullable: the endpoint used
    to keep only ltp and oi and discard the rest. IV is solved from the traded
    price with the same solver the leg quote uses, and is null where there is
    no trade.
    """
    ltp: Optional[float] = None
    ltp_change: Optional[float] = None
    ltp_change_pct: Optional[float] = None
    iv: Optional[float] = None
    oi: Optional[int] = None
    oi_change: Optional[int] = None
    oi_change_pct: Optional[float] = None
    volume: Optional[int] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    symbol: Optional[str] = None


class StrikeRow(BaseModel):
    """Strike row in an option chain."""
    strike: float
    ce: StrikeQuote
    pe: StrikeQuote


class OptionChainResponse(BaseModel):
    """Option chain snapshot for ONE expiry, the one asked for."""
    underlying: str
    expiry: str
    expiry_epoch: Optional[str] = Field(default=None, description="FYERS' epoch for this expiry, proof the right one was fetched")
    spot: float
    days_to_expiry: Optional[int] = None
    atm_strike: Optional[float] = None
    strikes: list[StrikeRow]
    total_call_oi: Optional[int] = None
    total_put_oi: Optional[int] = None
    pcr: Optional[float] = None
    max_pain: Optional[float] = None
    as_of: Optional[str] = None
    source: str = "FYERS optionchain"


class PositionResponse(BaseModel):
    """Open position record."""
    id: str
    strategy_name: str
    underlying: str
    legs: list[dict[str, Any]]
    net_debit_credit_inr: float
    max_loss_inr: float
    max_profit_inr: float
    breakeven_points: list[float]
    status: str
    mode: str
    opened_at: str
    unrealized_pnl_inr: Optional[float] = 0.0
    journal_path: Optional[str] = None
    # The broker margin this position took when it opened. None for a position
    # opened before migration 021, and None makes the desk's "margin used"
    # unavailable rather than a smaller figure that looks whole.
    margin_required_inr: Optional[float] = None
    margin_source: Optional[str] = None
    fill_basis: Optional[str] = None
    spot_at_entry: Optional[float] = None


# ---------------------------------------------------------------------------
# Journal and Lesson Ledger Models (BUILD-11)
# ---------------------------------------------------------------------------

class JournalTradeItem(BaseModel):
    position_id: str
    opened_at: str
    closed_at: Optional[str] = None
    strategy_name: str
    underlying: str = "NIFTY"
    legs_summary: str = ""
    entry_debit_credit_inr: float = 0.0
    # None, not 0.0. A trade that is still open, or one that is closed but has
    # no row in swayam_trade_history, has no result to show. Printing a zero
    # there is an invented figure on his record.
    gross_pnl_inr: Optional[float] = None
    net_pnl_inr: Optional[float] = None
    charges_inr: Optional[float] = None
    # Per leg: its own gross, its own entry and exit charges, its own net.
    # His instruction, 2026-09-09: "charges per leg, like profit/loss per leg".
    # Empty for a trade closed before charges were recorded this way.
    cost_legs: list[dict[str, Any]] = []
    rr_planned: Optional[float] = None
    rr_actual: Optional[float] = None
    time_in_trade_str: Optional[str] = None
    time_in_trade_minutes: Optional[int] = None
    points_in_trade: Optional[float] = None
    duration_days: Optional[float] = None
    status: str = "closed"
    outcome: Optional[str] = None  # WIN | LOSS | BREAKEVEN
    exit_reason: Optional[str] = None
    rules_followed: Optional[bool] = True
    rules_broken_reason: Optional[str] = None
    directional_view: Optional[str] = None
    setup_technical: Optional[str] = None
    setup_location: Optional[str] = None
    with_or_against_trend: Optional[str] = None
    moneyness_summary: Optional[str] = None
    entry_rationale: Optional[str] = None
    exit_rationale: Optional[str] = None
    journal_path: Optional[str] = None
    lesson_id: Optional[str] = None
    lesson_text: Optional[str] = None
    lesson_source: Optional[str] = None


class JournalKPIs(BaseModel):
    """His record. Every figure here is computed from SQUARED-OFF trades only.

    The rates are Optional on purpose. An empty book used to return a 0.0% win
    rate and a 100.0% discipline rate, and both render as real figures on a
    screen. Nothing known means nothing printed.
    """

    total_trades: int = 0          # squared-off trades, not rows matched
    wins_count: int = 0
    losses_count: int = 0
    breakeven_count: int = 0
    win_rate_pct: Optional[float] = None
    avg_rr_actual: Optional[float] = None
    cumulative_net_pnl_inr: float = 0.0
    cumulative_gross_pnl_inr: float = 0.0
    # Renamed from `cumulative_pnl_pct_of_margin`. It was divided by a hardcoded
    # 500000.0 that was neither his margin nor his capital; it is now his live
    # balance, so the name says capital and matches the divisor.
    cumulative_pnl_pct_of_capital: Optional[float] = None
    discipline_rate_pct: Optional[float] = None
    charges_drag_inr: float = 0.0
    charges_drag_pct: Optional[float] = None
    max_profit_trade: Optional[dict[str, Any]] = None
    max_loss_trade: Optional[dict[str, Any]] = None


class JournalTradesResponse(BaseModel):
    trades: list[JournalTradeItem]
    total_count: int
    kpis: JournalKPIs
    # What was left out of his record, and why, so the page can say it rather
    # than leaving him to wonder. His question, 2026-09-08: "I'm not aware of
    # how you are making a row... and I am never aware of it."
    excluded_test_rows: int = 0
    unpriced_closed_trades: int = 0
    capital_base_inr: Optional[float] = None
    capital_base_source: Optional[str] = None


class ArchiveTestTradesResponse(BaseModel):
    archived: int
    message: str


class LessonResponse(BaseModel):
    id: str
    position_id: str
    trade_closed_at: str
    strategy_name: str
    outcome: str
    realised_pnl_inr: float
    rr_planned: Optional[float] = None
    rr_actual: Optional[float] = None
    lesson_text: str
    lesson_source: str = "ai_generated"
    created_at: str
    updated_at: str


class LessonUpdateRequest(BaseModel):
    lesson_text: str

