"""
Pydantic data models for Swayam Capital Operational Readiness Check.
"""

from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class ReadinessInput(BaseModel):
    """Subjective pre-trade input submitted by Abhishek during the 60-second check."""

    sleep_hours_bucket: Literal["<3", "3-4", "4-5", "5-6", "6-7", "7+"]
    alcohol_yesterday: bool
    workout_in_last_48h: bool
    journal_mood: Literal["focused", "neutral", "tired", "off", "angry_grief"]
    life_stressor: Literal["none", "family", "work", "health", "financial", "other"]
    stressor_note: Optional[str] = None
    meditation_completed_at: Optional[datetime] = None
    logged_at: Optional[datetime] = None


class ReadinessVerdict(BaseModel):
    """Operational readiness verdict and sizing constraints for the trading session."""

    verdict: Literal["green", "yellow", "red"]
    trading_allowed: bool
    size_cap_pct: Optional[float] = None  # e.g., 0.01 for 1.0%, 0.0075 for 0.75%, None if blocked
    per_factor_verdicts: dict[str, Literal["green", "yellow", "red"]]
    reasons: list[str]
    method_rules_snapshot: dict[str, Any]


class FieldDelta(BaseModel):
    """Recorded difference between Abhishek's manual entry and end-of-day synced Atlas data."""

    field: str
    manual: Any
    atlas: Any
    delta: Optional[float] = None
    note: Optional[str] = None


class ReadinessReconciliation(BaseModel):
    """End-of-day reconciliation payload tracking subjective vs synced physical patterns."""

    log_date: str
    reconciled_at: str
    discrepancies: list[FieldDelta] = Field(default_factory=list)
    has_discrepancies: bool = False
