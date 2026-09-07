"""
Risk capital and the deployable margin ceiling, from the live broker account.

What this replaces
------------------
A single number typed into the Supabase config table, `margin_base_inr`, set to
Rs 8,50,000 and never updated. Every risk cap in the platform was a percentage
of that stale figure. On 2026-09-07 the real balance was Rs 9,71,002.38, so the
1% cap was being computed as Rs 8,500 instead of Rs 9,710.

Two numbers, two different jobs
-------------------------------
**Risk capital** answers "what are the 1% and 5% caps a percentage of?" It is
the total the account holds, `funds()` id 1 Total Balance. Abhishek's
instruction of 2026-09-07: risk appetite is measured against everything he
holds as margin, not against what he can deploy today.

**Deployable margin ceiling** answers "would the broker even accept this?" At
least half of the margin blocked for an F&O position must be cash or a cash
equivalent, so the ceiling is twice the cash-equivalent holding. A trade must
satisfy the risk cap AND fit inside this ceiling; failing either is a refusal,
with the reason named.

The one figure that cannot be derived, and why
----------------------------------------------
`funds()` reports total collateral as one line and does not split cash from
non-cash. `holdings()` reports MARKET value, not collateral value, and the
broker applies a different haircut to each instrument. On 2026-09-07 the liquid
ETF was worth Rs 59,999.40 at market but counted Rs 54,279.46 as collateral,
and the sovereign gold bond Rs 1,36,890.00 against Rs 1,23,201.00.

Inventing a haircut to bridge that gap would be fabricating a number, so this
module does not. The cash-equivalent pledged figure is stored, dated, and read
from Abhishek's FYERS collateral report. It is displayed with its age, it is
reconciled against the market value of the instruments actually classified as
cash-equivalent, and when it is too old it makes the ceiling unavailable rather
than quietly wrong.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from swayam.db import db

logger = logging.getLogger(__name__)

# funds() field ids, from the FYERS response, verified 2026-09-07.
FUND_TOTAL_BALANCE = 1
FUND_CLEAR_BALANCE = 3
FUND_COLLATERALS = 5
FUND_AVAILABLE_BALANCE = 10

# Instruments that count as cash equivalent for the exchange's cash rule:
# liquid funds and liquid ETFs, and sovereign gold bonds. Anything not listed
# here counts as non-cash, which is the conservative direction.
CASH_EQUIVALENT_SYMBOLS = (
    "LIQUIDBEES",
    "LIQUIDETF",
    "LIQUIDCASE",
    "SGB",  # sovereign gold bonds, e.g. NSE:SGBJUN30-GB
)

CONFIG_KEY_CASH_EQUIVALENT = "cash_equivalent_pledged_inr"
CASH_EQUIVALENT_MAX_AGE_DAYS = 45

# How far the stored collateral figure may sit from the market value of the
# instruments classified as cash equivalent before it is flagged. Haircuts on
# these instruments run around 10%, so a gap much beyond that means the stored
# figure is stale or the holdings have changed.
RECONCILE_TOLERANCE = 0.25

_lock = threading.Lock()
_snapshot: Optional["CapitalSnapshot"] = None


class CapitalUnavailable(RuntimeError):
    """Capital could not be established. Every caller must block, never default."""


@dataclass(frozen=True)
class CapitalSnapshot:
    """The account, as at one moment, with everything needed to show its provenance."""

    risk_capital_inr: float
    free_cash_inr: float
    collateral_inr: float
    cash_equivalent_pledged_inr: Optional[float]
    cash_equivalent_as_of: Optional[str]
    deployable_margin_ceiling_inr: Optional[float]
    ceiling_unavailable_reason: Optional[str]
    reconciliation_note: Optional[str]
    taken_at: datetime
    trading_day: date
    source: str = "FYERS funds() id 1 Total Balance"

    @property
    def primary_risk_cap_inr(self) -> float:
        """1% of risk capital. The cap a trade's stressed loss must sit under."""
        return round(self.risk_capital_inr * 0.01, 2)

    @property
    def black_swan_fuse_inr(self) -> float:
        """5% of risk capital. Raised from 3% on Abhishek's written instruction.

        His reasoning, recorded 2026-09-07: a black swan is a once-in-two-or-
        three-years event and as likely to favour him as not.
        """
        return round(self.risk_capital_inr * 0.05, 2)

    def as_dict(self) -> dict:
        return {
            "risk_capital_inr": round(self.risk_capital_inr, 2),
            "free_cash_inr": round(self.free_cash_inr, 2),
            "collateral_inr": round(self.collateral_inr, 2),
            "cash_equivalent_pledged_inr": self.cash_equivalent_pledged_inr,
            "cash_equivalent_as_of": self.cash_equivalent_as_of,
            "deployable_margin_ceiling_inr": self.deployable_margin_ceiling_inr,
            "ceiling_unavailable_reason": self.ceiling_unavailable_reason,
            "reconciliation_note": self.reconciliation_note,
            "primary_risk_cap_inr": self.primary_risk_cap_inr,
            "black_swan_fuse_inr": self.black_swan_fuse_inr,
            "taken_at": self.taken_at.isoformat(),
            "trading_day": self.trading_day.isoformat(),
            "source": self.source,
        }


def _read_funds() -> dict[int, float]:
    from swayam.fyers_client import FyersClient

    try:
        response = FyersClient().model.funds()
    except Exception as exc:
        raise CapitalUnavailable(f"Could not reach the broker for funds: {exc}") from exc

    if response.get("s") != "ok":
        raise CapitalUnavailable(
            f"Broker refused the funds request: {response.get('message') or response.get('code')}"
        )

    limits = response.get("fund_limit") or []
    if not limits:
        raise CapitalUnavailable("Broker returned no fund limits.")

    out: dict[int, float] = {}
    for row in limits:
        try:
            out[int(row["id"])] = float(row["equityAmount"])
        except (KeyError, TypeError, ValueError):
            continue
    if FUND_TOTAL_BALANCE not in out:
        raise CapitalUnavailable("Broker response carried no Total Balance.")
    return out


def _cash_equivalent_market_value() -> Optional[float]:
    """Market value of the holdings classified as cash equivalent.

    Used only to sanity-check the stored collateral figure, never as the figure
    itself: market value is not collateral value.
    """
    from swayam.fyers_client import FyersClient

    try:
        response = FyersClient().model.holdings()
    except Exception as exc:
        logger.warning("Could not read holdings for reconciliation: %s", exc)
        return None
    if response.get("s") != "ok":
        return None

    total = 0.0
    for row in response.get("holdings") or []:
        symbol = str(row.get("symbol", "")).upper()
        if any(token in symbol for token in CASH_EQUIVALENT_SYMBOLS):
            try:
                total += float(row.get("marketVal") or 0.0)
            except (TypeError, ValueError):
                continue
    return total or None


def _stored_cash_equivalent() -> tuple[Optional[float], Optional[str]]:
    """The dated cash-equivalent collateral figure from his FYERS report."""
    try:
        stored = db.get_config(CONFIG_KEY_CASH_EQUIVALENT)
    except Exception as exc:
        logger.warning("Could not read %s: %s", CONFIG_KEY_CASH_EQUIVALENT, exc)
        return None, None
    if not isinstance(stored, dict):
        return None, None
    try:
        return float(stored["amount_inr"]), str(stored["as_of"])
    except (KeyError, TypeError, ValueError):
        return None, None


def get_capital(*, force: bool = False) -> CapitalSnapshot:
    """Returns the capital snapshot for the current trading day.

    Snapshotted once per trading day so a mid-session balance change never
    retroactively alters the permitted risk of a trade already open.

    Raises:
        CapitalUnavailable: if the broker cannot be reached. Callers block.
    """
    global _snapshot

    today = datetime.now(timezone.utc).astimezone().date()
    with _lock:
        if _snapshot is not None and not force and _snapshot.trading_day == today:
            return _snapshot

    funds = _read_funds()
    risk_capital = funds[FUND_TOTAL_BALANCE]
    if risk_capital <= 0:
        raise CapitalUnavailable("Broker reported a Total Balance of zero or less.")

    free_cash = funds.get(FUND_CLEAR_BALANCE, 0.0)
    collateral = funds.get(FUND_COLLATERALS, 0.0)

    pledged, as_of = _stored_cash_equivalent()
    ceiling: Optional[float] = None
    ceiling_reason: Optional[str] = None
    reconciliation: Optional[str] = None

    if pledged is None:
        ceiling_reason = (
            "The cash-equivalent collateral figure has never been recorded. "
            "It cannot be derived: the broker reports collateral as one total and "
            "holdings at market value, not collateral value. Enter it from the "
            "FYERS collateral report."
        )
    else:
        try:
            as_of_date = date.fromisoformat(as_of or "")
        except ValueError:
            as_of_date = None

        if as_of_date is None:
            ceiling_reason = "The cash-equivalent collateral figure carries no usable date."
        elif today - as_of_date > timedelta(days=CASH_EQUIVALENT_MAX_AGE_DAYS):
            ceiling_reason = (
                f"The cash-equivalent collateral figure is from {as_of_date:%d %b %Y}, "
                f"more than {CASH_EQUIVALENT_MAX_AGE_DAYS} days old. Refresh it from the "
                f"FYERS collateral report."
            )
        else:
            # At least half of blocked margin must be cash or cash equivalent,
            # so the cash side supports twice itself in total margin.
            ceiling = round(2.0 * (free_cash + pledged), 2)

            market = _cash_equivalent_market_value()
            if market and pledged > 0:
                drift = abs(market - pledged) / pledged
                if drift > RECONCILE_TOLERANCE:
                    reconciliation = (
                        f"The stored cash-equivalent collateral of ₹{pledged:,.0f} is "
                        f"{drift * 100:.0f}% away from the ₹{market:,.0f} market value of the "
                        f"instruments classified as cash equivalent. Worth re-checking "
                        f"against the FYERS collateral report."
                    )

    snapshot = CapitalSnapshot(
        risk_capital_inr=risk_capital,
        free_cash_inr=free_cash,
        collateral_inr=collateral,
        cash_equivalent_pledged_inr=pledged,
        cash_equivalent_as_of=as_of,
        deployable_margin_ceiling_inr=ceiling,
        ceiling_unavailable_reason=ceiling_reason,
        reconciliation_note=reconciliation,
        taken_at=datetime.now(timezone.utc),
        trading_day=today,
    )
    with _lock:
        _snapshot = snapshot
    return snapshot
