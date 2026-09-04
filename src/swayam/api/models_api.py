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


class PayoffCurveResponse(BaseModel):
    """Full payoff curve analysis."""
    spot_range: list[float]
    points: list[PayoffPointResponse]
    breakevens: list[float]
    max_profit_inr: float
    max_loss_inr: float
    rr_implied: float
    net_debit_credit_inr: float


class GreeksResponse(BaseModel):
    """Standardized aggregated portfolio Greeks."""
    net_delta: float
    net_gamma: float
    net_theta_per_day: float
    net_vega: float
    net_rho: float


class StrategyComputeResponse(BaseModel):
    """Combined strategy computation output."""
    payoff_curve: PayoffCurveResponse
    greeks: GreeksResponse


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
