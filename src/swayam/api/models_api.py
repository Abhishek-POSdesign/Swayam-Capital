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
    entry_premium: float = Field(default=0.0, ge=0.0, description="Option premium per share")
    expiry_date: str = Field(..., description="Expiration date in YYYY-MM-DD format")
    lot_size: int = Field(default=75, ge=1, description="Underlying lot size")

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
    iv_shift_pct: float = Field(
        default=0.0,
        description="Optional IV percentage shift [-90, +200] for stress-testing payoff curve",
    )


class ExecuteRequest(StrategyComputeRequest):
    """Payload for executing a trade (paper or real)."""
    mode: str = Field(default="paper", description="Execution mode: 'paper' or 'real'")
    order_type: str = Field(default="LIMIT", description="Order type: 'LIMIT' or 'MARKET'")
    session_id: Optional[str] = Field(default=None, description="Active AI session ID to link to trade")


class PreviewLegItem(BaseModel):
    """Individual leg specification for pre-execution sequence preview."""
    strike: float = Field(..., description="Strike price in rupees")
    option_type: str = Field(..., description="CE or PE")
    direction: str = Field(..., description="buy or sell")
    quantity_lots: int = Field(default=1, ge=1, description="Quantity in lots")
    entry_premium: float = Field(default=0.0, ge=0.0, description="Option premium per share")
    expiry_date: str = Field(..., description="Expiration date YYYY-MM-DD")
    lot_size: int = Field(default=75, ge=1, description="Lot size")
    order_type: str = Field(default="LIMIT", description="LIMIT or MARKET")


class MultiLegPreviewRequest(BaseModel):
    """Request payload to simulate and order legs for margin safety."""
    underlying: str = Field(default="NIFTY", description="Underlying symbol")
    current_spot: float = Field(..., gt=0.0, description="Current spot price")
    legs: list[PreviewLegItem] = Field(..., min_length=1, description="Strategy legs to order")


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
    estimated_margin_inr: float
    action_note: str


class MultiLegPreviewResponse(BaseModel):
    """Output with legs sorted BUY first and margin analysis."""
    ordered_legs: list[OrderedLegStep]
    buy_count: int
    sell_count: int
    total_debit_credit_inr: float
    initial_margin_required_inr: float
    final_hedged_margin_inr: float
    margin_saved_inr: float


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


class RiskVerdict(BaseModel):
    """Verdict and metrics for a risk cap evaluation."""
    loss_inr: float
    cap_inr: float
    pct_of_margin: float
    passed: bool


class ValidationResponse(BaseModel):
    """Complete rule compliance audit for an options spread."""
    passed: bool
    overall_passed: bool
    realistic_risk: RiskVerdict
    blast_radius: RiskVerdict
    checks: list[ValidationCheck]
    warnings: list[str] = []


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
    """Individual option leg Greek metrics."""
    strike: float
    option_type: str
    direction: str
    delta: float
    theta: float
    vega: float
    gamma: float


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


class StrikeQuote(BaseModel):
    """Quote for an option contract."""
    ltp: float
    iv: float
    oi: int


class StrikeRow(BaseModel):
    """Strike row in an option chain."""
    strike: float
    ce: StrikeQuote
    pe: StrikeQuote


class OptionChainResponse(BaseModel):
    """Option chain snapshot."""
    underlying: str
    expiry: str
    spot: float
    strikes: list[StrikeRow]


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
    gross_pnl_inr: float = 0.0
    net_pnl_inr: float = 0.0
    charges_inr: float = 0.0
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
    total_trades: int = 0
    wins_count: int = 0
    losses_count: int = 0
    breakeven_count: int = 0
    win_rate_pct: float = 0.0
    avg_rr_actual: float = 0.0
    cumulative_net_pnl_inr: float = 0.0
    cumulative_gross_pnl_inr: float = 0.0
    cumulative_pnl_pct_of_margin: float = 0.0
    discipline_rate_pct: float = 100.0
    charges_drag_inr: float = 0.0
    charges_drag_pct: float = 0.0
    max_profit_trade: Optional[dict[str, Any]] = None
    max_loss_trade: Optional[dict[str, Any]] = None


class JournalTradesResponse(BaseModel):
    trades: list[JournalTradeItem]
    total_count: int
    kpis: JournalKPIs
    pre_launch_test_trades_count: int = 0


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

