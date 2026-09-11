"""The exchange's daily price band for one contract, and the tick it trades on.

WHY THIS EXISTS
---------------
A resting order is a price he chose that the market has not reached. The
exchange will not accept every such price: each contract has a daily circuit,
a lower and an upper limit, and a tick size. An order outside the band or off
the tick would be rejected by a real broker, so the terminal refuses it here,
with the band named, rather than letting him believe something is waiting for
a price that could never trade.

WHERE THE BAND COMES FROM. Settled by a read-only test against live FYERS on
2026-09-10 evening, and it is not where you would look first:

  * The FYERS QUOTE call carries NO band at all. Its fields are ask, atp, bid,
    ch, chp, high_price, low_price, lp, open_price, prev_close_price, spread,
    volume and the names. There is nothing about a circuit in it.
  * The FYERS MARKET DEPTH call does. `model.depth(data={"symbol": sym,
    "ohlcv_flag": "1"})` answers, keyed by the symbol, with `lower_ckt`,
    `upper_ckt` and `tick_Size` beside `bids`, `ask`, `ltp`, `oi`, `pdoi`,
    `totalbuyqty` and `totalsellqty`. For NSE:NIFTY26SEP23800CE at the close
    on 10 September: lower 0.05, upper 263.85, tick 0.05.

ONE CALL, AT PLACEMENT, NEVER ON A REFRESH. The band is read once when the
order is placed and stored on the order. The watcher never reads it again, so
this costs one FYERS request per order placed and nothing per tick. It does
not touch the chain feed's budget.

AND WHEN IT CANNOT BE READ. The order still rests, `band_source` is recorded
as `unavailable`, and the screen says "band not readable from FYERS; the order
rests without a band check". A band is NEVER invented, never defaulted, never
carried over from another strike. His first rule: every number real, or
unavailable with the reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import logging
import math
from typing import Any, Optional

logger = logging.getLogger(__name__)

FYERS_DEPTH = "FYERS depth"
UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class PriceBand:
    """What the exchange will accept for this contract today, or why it is unknown."""

    lower: Optional[float]
    upper: Optional[float]
    tick: Optional[float]
    source: str                    # FYERS_DEPTH or UNAVAILABLE
    symbol: Optional[str] = None
    reason: Optional[str] = None   # why it is unavailable, in his words

    @property
    def known(self) -> bool:
        return self.source == FYERS_DEPTH and self.lower is not None and self.upper is not None

    def describe(self) -> str:
        """One line for the screen. Either the band or the honest gap."""
        if self.known:
            return f"inside today's band, {self.lower:,.2f} to {self.upper:,.2f}"
        return "band not readable from FYERS; the order rests without a band check"


def _num(value: Any) -> Optional[float]:
    """A real number, or None. Zero is a real lower circuit, so zero is kept."""
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out >= 0 else None


def _pick(row: dict[str, Any], *names: str) -> Optional[float]:
    """The first of these fields FYERS actually published."""
    for name in names:
        if name in row:
            found = _num(row.get(name))
            if found is not None:
                return found
    return None


def band_for_symbol(symbol: str) -> PriceBand:
    """The band and tick for one FYERS symbol, from the market depth call.

    Never raises. A failure is an unavailable band with the reason on it,
    because a band that cannot be read must not stop him placing an order.
    """
    from swayam.fyers_client import fyers_client

    try:
        response: dict[str, Any] = fyers_client.model.depth(
            data={"symbol": symbol, "ohlcv_flag": "1"}
        )
    except Exception as exc:  # noqa: BLE001 - any failure is the same answer
        logger.warning("Depth call failed for %s: %s", symbol, exc)
        return PriceBand(None, None, None, UNAVAILABLE, symbol=symbol, reason=str(exc))

    if not isinstance(response, dict) or str(response.get("s", "")).lower() not in ("ok", ""):
        message = str(response.get("message") or response) if isinstance(response, dict) else str(response)
        logger.warning("Depth call refused for %s: %s", symbol, message)
        return PriceBand(None, None, None, UNAVAILABLE, symbol=symbol, reason=message)

    payload = response.get("d") if isinstance(response.get("d"), dict) else response
    row = payload.get(symbol) if isinstance(payload, dict) else None
    if not isinstance(row, dict):
        # Some responses key on the symbol without the exchange prefix, and a
        # single-symbol answer sometimes arrives unkeyed. Take the only row
        # rather than guess a name, and say so when there is no row at all.
        rows = [v for v in payload.values() if isinstance(v, dict)] if isinstance(payload, dict) else []
        if len(rows) == 1:
            row = rows[0]
        else:
            return PriceBand(
                None, None, None, UNAVAILABLE, symbol=symbol,
                reason=f"FYERS depth carried no row for {symbol}.",
            )

    lower = _pick(row, "lower_ckt", "lowerCkt", "lower_circuit")
    upper = _pick(row, "upper_ckt", "upperCkt", "upper_circuit")
    tick = _pick(row, "tick_Size", "tick_size", "tickSize")
    if lower is None or upper is None or upper <= 0:
        return PriceBand(
            None, None, tick, UNAVAILABLE, symbol=symbol,
            reason="FYERS depth answered without a circuit for this contract.",
        )
    return PriceBand(lower, upper, tick, FYERS_DEPTH, symbol=symbol)


def band_for_leg(
    *,
    underlying: str,
    expiry: str,
    strike: float,
    option_type: str,
) -> PriceBand:
    """The band for one option leg, resolving its symbol from the contract master.

    The symbol is read from the FYERS master rather than assembled from a
    format string, because weekly and monthly expiries encode differently and
    a hand-built symbol is a silent source of the wrong contract's band.
    """
    from swayam.services.contract_master import ContractMasterUnavailable, get_symbol

    try:
        expiry_date = _as_date(expiry)
    except ValueError as exc:
        return PriceBand(None, None, None, UNAVAILABLE, reason=str(exc))

    try:
        symbol = get_symbol(underlying or "NIFTY", expiry_date, float(strike), option_type)
    except ContractMasterUnavailable as exc:
        return PriceBand(None, None, None, UNAVAILABLE, reason=str(exc))
    except Exception as exc:  # noqa: BLE001
        return PriceBand(None, None, None, UNAVAILABLE, reason=str(exc))

    return band_for_symbol(symbol)


def _as_date(value: str) -> date:
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{value!r} is not a date this build can read.") from exc


def check_price(band: PriceBand, price: float) -> Optional[str]:
    """Why this price cannot rest, or None when it can.

    Two reasons only, both facts about the exchange rather than rules of his:
    outside the day's circuit, and not on the tick. An unknown band refuses
    nothing, because refusing on a number nobody could read would be the
    terminal inventing a limit.
    """
    if not band.known:
        return None

    if price < band.lower or price > band.upper:
        return (
            f"{price:,.2f} is outside today's price band for this contract, which is "
            f"{band.lower:,.2f} to {band.upper:,.2f} from FYERS. The exchange would not "
            f"hold an order there. Move the price inside the band."
        )

    tick = band.tick
    if tick and tick > 0:
        steps = price / tick
        # Prices arrive as floats, so a price exactly on the tick can land a
        # hair either side of a whole number of steps. A thousandth of a tick
        # is the tolerance; anything looser would let a real off-tick price
        # through.
        if abs(steps - round(steps)) > 1e-3:
            below = math.floor(steps) * tick
            above = math.ceil(steps) * tick
            return (
                f"{price:,.2f} is not on this contract's tick of {tick:,.2f}. "
                f"The nearest prices that trade are {below:,.2f} and {above:,.2f}."
            )
    return None
