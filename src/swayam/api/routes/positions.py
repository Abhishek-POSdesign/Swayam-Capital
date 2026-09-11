"""
Portfolio and active positions endpoints for Swayam Capital (BUILD-7).

Provides:
- GET  /api/positions       — List positions from Supabase & local cache
- GET  /api/positions/live  — Real-time positions list with live P&L and Greeks from FYERS
- GET  /api/positions/{id}/pnl-live — Single position live P&L
- POST /api/positions/{id}/close   — Close position with DB-before-journal ordering
"""

from datetime import date, datetime, timezone
import logging
import time
import uuid
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from swayam.api.journal_writer import append_exit_block
from swayam.services.execution_safety import mark_journal_status, queue_journal_note
from swayam.services.structure_name import is_open as _leg_is_open, name_from_legs, resolve_name
from swayam.services.exit_refusal import is_his_price, reword_if_his_price
from swayam.services.phase import read_phase
from swayam.services.targets import evaluate_position as evaluate_targets
from swayam.services.targets import wrong_side_of_entry
from swayam.services.fills import FillRefused, LegQuote, exit_side_of, resolve_fill, spread_cost_inr
from swayam.services.charges import (
    ChargeScheduleUnavailable,
    charge_for_leg,
    opposite,
    side_from_direction,
)
from swayam.api.models_api import PositionResponse
from swayam.config import settings
from swayam.db import db
from swayam.fyers_client import FyersClientError, fyers_client
from swayam.options_math.greeks import compute_position_greeks
from swayam.services import capital as capital_service
from swayam.services.capital import CapitalUnavailable
from swayam.options_math.models import Direction, Leg, OptionType, Spread

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory store for paper positions in local mode
_local_paper_positions: list[dict[str, Any]] = []

# What FYERS calls the indices. A position row stores "NIFTY"; the option-chain
# API wants the full symbol and rejects anything else.
# Expiry date -> FYERS epoch, cached for ten minutes. Resolving it costs a
# call, and the desk polls positions every few seconds.
_expiry_epoch_cache: dict[str, tuple[str, float]] = {}

_FYERS_INDEX_SYMBOLS = {
    "NIFTY": "NSE:NIFTY50-INDEX",
    "NIFTY50": "NSE:NIFTY50-INDEX",
    "BANKNIFTY": "NSE:NIFTYBANK-INDEX",
    "FINNIFTY": "NSE:FINNIFTY-INDEX",
    "SENSEX": "BSE:SENSEX-INDEX",
}

# 5-second in-memory cache for FYERS option chains
# key: f"{underlying}_{expiry}" -> {"data": raw_chain, "timestamp": float}
_chain_cache: dict[str, dict[str, Any]] = {}


def record_local_paper_position(pos: dict[str, Any]) -> None:
    """Adds a paper position to the in-memory session cache after a successful Supabase insert.

    Merged with the Supabase read in get_positions() so a container without a warm DB
    connection still sees positions opened during this session.
    """
    _local_paper_positions.append(pos)


# ---------------------------------------------------------------------------
# Models for live P&L and Close flow
# ---------------------------------------------------------------------------

class LivePositionGreeks(BaseModel):
    net_delta: float
    net_gamma: float
    net_theta_per_day: float
    net_vega: float


class LivePositionResponse(BaseModel):
    """One open trade, marked at the price he would actually get.

    Build A part one added everything the position card on the desk reads, so
    the browser never computes money: the per-leg mark and which side of the
    book it is, what getting out would cost at that mark, the trade's net if
    he exits now, rule 1's headroom against the live balance, and the market
    state, which is the only thing that may put the word LIVE on a screen.

    Every money field is Optional for one reason: a figure that cannot be read
    is None with `error` saying why, never a zero and never a partial sum.
    """

    position_id: str
    strategy_name: str
    name_source: str = "structure"
    underlying: str
    opened_at: str
    expiry_date: Optional[str] = None
    legs: list[dict[str, Any]]
    entry_debit_credit_inr: float
    # NONE MEANS NO CEILING, and the card prints the word unlimited. Coercing
    # it to 0.0 was the real danger of fault 0a: a naked short would have read
    # "max loss zero", which is the most reassuring wrong number this terminal
    # could possibly show.
    max_loss_inr: Optional[float] = None
    max_loss_unbounded_reason: Optional[str] = None
    max_profit_inr: float
    breakevens: list[float] = []
    current_spot: Optional[float] = None
    spot_at_entry: Optional[float] = None
    current_position_value_inr: Optional[float] = None
    unrealized_pnl_inr: Optional[float] = None
    unrealized_pnl_pct_of_risk: Optional[float] = None

    # What the round trip costs, both ways, and what is actually left.
    charges_in_inr: Optional[float] = None
    charges_out_now_inr: Optional[float] = None
    net_if_exit_now_inr: Optional[float] = None

    # The rules, as percentages of the balance read fresh this session.
    rule1_cap_inr: Optional[float] = None
    rule1_headroom_inr: Optional[float] = None
    rule4_ceiling_inr: Optional[float] = None
    rules_unavailable_reason: Optional[str] = None

    margin_required_inr: Optional[float] = None
    margin_source: Optional[str] = None
    provenance: Optional[str] = None
    fill_basis: Optional[str] = None

    # A trade is a campaign: some legs may already be squared off.
    legs_open: int = 0
    legs_closed: int = 0

    current_greeks: Optional[LivePositionGreeks] = None
    greeks_unavailable_reason: Optional[str] = None
    days_held: int
    days_remaining_to_expiry: int
    journal_path: Optional[str] = None

    # Why the cost of the round trip could not be read, when the profit could.
    charges_unavailable_reason: Optional[str] = None

    # WHAT HE ASKED THIS TRADE TO TELL HIM, and whether it has.
    #
    # `state` is running | alert | quiet and is decided on the SERVER, so Home
    # and the desk cannot disagree about the same trade. `alerts` names every
    # target reached, leg by leg and then the trade. `targets` is what is set.
    # services/targets.py has the rules; nothing here recomputes them.
    state: str = "quiet"
    alerts: list[dict[str, Any]] = []
    targets: Optional[dict[str, Any]] = None

    # BUILD B. How many orders are still waiting on this trade, which is the
    # count Home's band shows as its third figure, and the line the bell puts
    # there when a resting exit expired and left a leg he meant to be out of.
    # Both are filled in by `_attach_resting_counts` from ONE read of the
    # order book, so neither screen counts anything for itself.
    resting_orders: int = 0
    orders_warning: Optional[str] = None

    # live | closing. Nothing may print LIVE unless this says live.
    market_state: str = "closing"
    read_at: Optional[str] = None
    error: Optional[str] = None


class CloseLegItem(BaseModel):
    """One leg's exit instruction.

    Three shapes, and the difference matters to his record:

      * `exit_premium` alone - a price HE supplied, from a terminal or a
        script. Recorded as supplied, never dressed up as a market fill.
      * `order_type: "MARKET"` - filled against the book reversed, a bought
        leg sold at the bid and a sold leg bought back at the ask.
      * `order_type: "LIMIT"` with `limit_price` - fills at his price or
        better. A limit the book has not reached refuses the whole send in
        this build; Build B rests it instead.

    His addition of 2026-09-09 evening: "exiting a single leg or exiting all
    legs should have a limit/market price option."
    """

    strike: float
    option_type: str
    exit_premium: Optional[float] = None
    order_type: Optional[str] = None
    limit_price: Optional[float] = None

    @property
    def is_supplied(self) -> bool:
        """A price he handed over, rather than an order to fill against a book."""
        return self.exit_premium is not None and not self.order_type


class ClosePositionRequest(BaseModel):
    close_reason: str = Field(
        default="manual",
        description="Trigger: 'target_hit', 'stop_hit', 'time_exit', 'manual'",
    )
    notes: Optional[str] = None
    exit_legs: Optional[list[CloseLegItem]] = None


class ClosePositionResponse(BaseModel):
    """What a close actually cost and made, in the three lines he asked for.

    Cumulative gross, cumulative charges for the whole round trip, and the net
    after them. `exit_legs` carries the same three figures for each individual
    leg, because a charge belongs to the leg that incurred it.
    """

    position_id: str
    status: str
    gross_pnl_inr: float = 0.0
    realized_pnl_inr: float
    total_charges_inr: float
    exit_legs: list[dict[str, Any]] = []
    journal_path: Optional[str] = None
    lesson: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Helper: Option Chain Fetch with 5s caching
# ---------------------------------------------------------------------------


def _get_cached_option_chain(underlying: str, expiry: Optional[str] = None) -> dict[str, Any]:
    """The chain for a position's expiry, READ FROM THE SHARED FEED.

    FAULT 0b of his live test, 11 September 2026. FYERS began refusing from
    about 15:00 with code 429, "request limit reached", and it cost him a
    refused exit at the one time of day he is at the screen.

    This function used to call `fyers_client.get_option_chain` itself, twice:
    once at strike_count=2 to resolve the expiry epoch, once at 40 for the
    chain, behind a five-second cache. His pages poll every FIVE seconds, so
    that cache had almost always just expired when the next poll arrived and
    nearly every poll became a live broker call. `api/chain_feed.py` was built
    on 8 September for exactly this, after the same thing happened then, and
    this path was simply never moved onto it.

    Now it registers interest and reads whatever the feed last fetched. One
    call per expiry per interval however many browsers, tabs, positions or
    legs are watching, shared with the option chain panel and with Build B's
    order watcher, which already ride the feed. When FYERS refuses, the feed
    stands back and keeps the last real chain with its true age attached
    rather than hammering a broker that is saying no.

    Nothing here invents a price. A feed with no chain at all raises, and the
    caller says unavailable with the reason, exactly as before.
    """
    # Imported here rather than at module scope: market.py imports from this
    # module, and a top-level import either way closes the circle.
    from swayam.api.routes.market import WIDE_CHAIN_STRIKES, epoch_for, fetch_chain_cached

    symbol = _FYERS_INDEX_SYMBOLS.get(str(underlying).upper(), str(underlying))

    try:
        epoch: Optional[str] = None
        if expiry:
            # The date-to-epoch mapping, remembered for ten minutes, so this
            # does not re-read a chain every five seconds to learn a fact that
            # changes once a week.
            epoch = epoch_for(symbol, str(expiry))
            if not epoch:
                logger.warning(
                    "FYERS did not list an expiry on %s; reading the chain without one.",
                    expiry,
                )

        return fetch_chain_cached(symbol, WIDE_CHAIN_STRIKES, epoch)
    except Exception as e:
        logger.error("FYERS option chain query failed for %s (%s): %s", underlying, expiry, e)
        raise HTTPException(
            status_code=503,
            detail="Cannot compute live P&L: FYERS chain unreachable. Try again in a moment.",
        ) from e


def _build_chain_lookup(raw_chain: dict[str, Any]) -> tuple[float, dict[tuple[float, str], dict[str, Any]]]:
    """Flattens FYERS option chain into a (strike, option_type) -> quote lookup map."""
    spot = float(raw_chain.get("underlyingValue") or raw_chain.get("spot") or 0.0)
    options_chain = raw_chain.get("optionsChain") or raw_chain.get("strikes") or []
    lookup: dict[tuple[float, str], dict[str, Any]] = {}

    def _num(value: Any) -> Optional[float]:
        """A real number, or None. Never a substitute.

        This used to default a missing last-traded price to 0.0 and a missing
        implied volatility to 0.15. A price of zero is not "no price", it is a
        claim that the option is worthless, and it flowed straight into
        position P&L. A volatility of 0.15 was simply invented.
        """
        if value is None:
            return None
        try:
            num = float(value)
        except (TypeError, ValueError):
            return None
        return num if num > 0 else None

    for item in options_chain:
        strike = float(item.get("strike_price") or item.get("strike") or 0.0)

        # Dual CE/PE format (FYERS standard optionsChain item)
        # The bid and the ask travel with the last trade. An exit is filled
        # against the book (a bought leg sold at the bid, a sold leg bought
        # back at the ask), never at the last trade. PR 2, 2026-09-09.
        if "call_ltp" in item or "call_symbol" in item:
            lookup[(strike, "CE")] = {
                "ltp": _num(item.get("call_ltp")),
                "iv": _num(item.get("call_iv")),
                "bid": _num(item.get("call_bid")),
                "ask": _num(item.get("call_ask")),
            }
        if "put_ltp" in item or "put_symbol" in item:
            lookup[(strike, "PE")] = {
                "ltp": _num(item.get("put_ltp")),
                "iv": _num(item.get("put_iv")),
                "bid": _num(item.get("put_bid")),
                "ask": _num(item.get("put_ask")),
            }

        # Nested CE/PE format (models_api StrikeRow item)
        if "ce" in item and isinstance(item["ce"], dict):
            lookup[(strike, "CE")] = {
                "ltp": _num(item["ce"].get("ltp")),
                "iv": _num(item["ce"].get("iv")),
                "bid": _num(item["ce"].get("bid")),
                "ask": _num(item["ce"].get("ask")),
            }
        if "pe" in item and isinstance(item["pe"], dict):
            lookup[(strike, "PE")] = {
                "ltp": _num(item["pe"].get("ltp")),
                "iv": _num(item["pe"].get("iv")),
                "bid": _num(item["pe"].get("bid")),
                "ask": _num(item["pe"].get("ask")),
            }

        # Single contract item
        if "option_type" in item and "ltp" in item:
            lookup[(strike, str(item["option_type"]).upper())] = {
                "ltp": _num(item.get("ltp")),
                "iv": _num(item.get("iv")),
                "bid": _num(item.get("bid")),
                "ask": _num(item.get("ask")),
            }

    return spot, lookup


def _market_is_open_now() -> bool:
    """Whether NIFTY options are trading right now, in IST.

    A close is a fill, and a fill against the closing book is one nobody could
    have got.

    ONE CLOCK, NOT TWO. This used to be its own copy of the market hours,
    beside an identical copy in `spot_feed.market_is_open`, which is the one
    `/api/market/data-health` answers from. Two copies of a rule is how the
    dead expiry survived being fixed at one route: they agreed today and there
    was nothing to stop them disagreeing tomorrow. This now delegates, so the
    position area, the close and the data-health strip cannot drift apart.
    """
    from swayam.api.chain_feed import market_is_open

    return market_is_open()


def _opt_float(value: Any) -> Optional[float]:
    """A real number, or None. Never a substitute, never a zero standing in."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _days_held(opened_at_str: str) -> int:
    try:
        opened = datetime.fromisoformat(str(opened_at_str).replace("Z", "+00:00"))
        return max(0, (datetime.now(timezone.utc).date() - opened.date()).days)
    except Exception:
        return 0


def _days_to_expiry(expiry_val: Any) -> int:
    try:
        if not expiry_val:
            return 0
        exp = datetime.fromisoformat(str(expiry_val)).date()
        return max(0, (exp - date.today()).days)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def _ids_the_database_knows(ids: set[str]) -> set[str]:
    """Which of these positions the database has ever heard of, at any status.

    THE GHOST, found 2026-09-09. `_local_paper_positions` is an in-process list
    written when a trade opens. The merge below only skipped a local copy if the
    same id was ALREADY in the database result, and that result holds open rows
    only. So once a position closed, the database stopped returning it, the
    stale in-memory copy stopped being skipped, and Home showed a position that
    had been closed for half an hour.

    Worse, it is per process: his trade was closed from his PC, so the Cloud Run
    instance still had `status: open` in its own memory and had no way to learn
    otherwise.

    The database is the truth. The local list is a fallback for when the
    database cannot be reached, and it must never shadow it.
    """
    if not ids:
        return set()
    try:
        res = db.client.table("swayam_positions").select("id").in_("id", sorted(ids)).execute()
        return {str(r["id"]) for r in (res.data or [])}
    except Exception as exc:
        logger.warning("Could not check the database for local position ids: %s", exc)
        return set()


def _results_for(positions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The recorded result of each of these trades, by position id.

    One trade has one result row, so the newest wins if a row were ever
    duplicated; the close path forbids that, and this does not paper over it.
    A database that cannot be read gives an empty map, and every figure then
    says unavailable rather than zero.
    """
    ids = [str(p.get("id")) for p in positions if p.get("id")]
    if not ids:
        return {}
    try:
        res = (
            db.client.table("swayam_trade_history")
            .select("position_id,closed_at,close_reason,realized_pnl_inr,total_charges_inr,holding_days")
            .in_("position_id", ids)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read the recorded results for these positions: %s", exc)
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in res.data or []:
        out[str(row.get("position_id"))] = row
    return out


@router.get("/api/positions", response_model=list[PositionResponse])
def get_positions(status: str = Query(default="open")) -> list[PositionResponse]:
    """Returns list of positions with current unrealized P&L."""
    positions_data: list[dict[str, Any]] = []

    # Attempt fetching from Supabase
    try:
        client = db.client
        res = client.table("swayam_positions").select("*").eq("status", status).execute()
        if res.data:
            positions_data.extend(res.data)
    except Exception as exc:
        logger.error("Could not fetch positions from Supabase: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "Positions service unavailable: cannot reach Supabase to fetch positions. "
                "Do not assume 'no positions' when database is unreachable. "
                f"Underlying error: {exc}"
            ),
        ) from exc

    # Merge local session paper trades ONLY where the database has never heard
    # of them. A local copy must never shadow a row the database owns.
    existing_ids = {str(p.get("id")) for p in positions_data}
    local_ids = {str(l.get("id")) for l in _local_paper_positions} - existing_ids
    known = _ids_the_database_knows(local_ids)
    for local_pos in _local_paper_positions:
        pid = str(local_pos.get("id"))
        if pid in existing_ids or pid in known:
            continue
        if local_pos.get("status") == status:
            positions_data.append(local_pos)

    # A CLOSED TRADE CARRIES ITS RESULT. One query for all of them rather than
    # one per row, because the desk asks for this list every few seconds.
    results_by_id = _results_for(positions_data) if status == "closed" else {}

    results: list[PositionResponse] = []
    for p in positions_data:
        outcome = results_by_id.get(str(p.get("id")), {})
        net = _opt_float(outcome.get("realized_pnl_inr"))
        charges = _opt_float(outcome.get("total_charges_inr"))
        results.append(
            PositionResponse(
                closed_at=str(outcome["closed_at"]) if outcome.get("closed_at") else p.get("closed_at"),
                close_reason=outcome.get("close_reason") or p.get("exit_reason"),
                realized_pnl_inr=net,
                total_charges_inr=charges,
                # The net IS the gross less the charges, so adding them back is
                # exact rather than a reconstruction.
                gross_pnl_inr=(round(net + charges, 2) if net is not None and charges is not None else None),
                holding_days=(
                    int(outcome["holding_days"]) if outcome.get("holding_days") is not None else None
                ),
                id=str(p.get("id")),
                # THE NAME FOLLOWS THE LEGS unless he typed one himself, on a
                # closed trade as much as an open one. Without this a spread
                # stored before migration 022 keeps whatever the preset left
                # behind, which is how his condor came to be called "Short
                # Strangle" and a bull put spread reads "Custom".
                strategy_name=resolve_name(
                    p.get("legs") or [],
                    name_source=str(p.get("name_source") or "structure"),
                    current_name=p.get("strategy_name"),
                    # A closed trade is named by every leg it held, not by the
                    # open ones, because it has none left.
                    closed=str(p.get("status") or "").lower() == "closed",
                )
                or "Unknown Strategy",
                name_source=str(p.get("name_source") or "structure"),
                # What this trade was: live, terminal_test or build_test. The
                # card reads it to say so, and said "not recorded" without it.
                provenance=p.get("provenance"),
                underlying=p.get("underlying", "NIFTY"),
                legs=p.get("legs", []),
                net_debit_credit_inr=float(p.get("net_debit_credit_inr", 0.0)),
                max_loss_inr=_opt_float(p.get("max_loss_inr")),
                max_loss_unbounded_reason=p.get("max_loss_unbounded_reason"),
                max_profit_inr=float(p.get("max_profit_inr", 0.0)),
                breakeven_points=p.get("breakeven_points", []),
                status=p.get("status", "open"),
                mode=p.get("mode", "paper"),
                opened_at=str(p.get("opened_at")),
                unrealized_pnl_inr=float(p.get("unrealized_pnl_inr", 0.0)),
                journal_path=p.get("journal_path"),
                # Stored from migration 021 on. None for anything older, and the
                # desk turns one None into "margin used unavailable" rather than
                # a smaller figure that looks whole.
                margin_required_inr=(
                    float(p["margin_required_inr"]) if p.get("margin_required_inr") is not None else None
                ),
                margin_source=p.get("margin_source"),
                fill_basis=p.get("fill_basis"),
                spot_at_entry=(
                    float(p["spot_at_entry"]) if p.get("spot_at_entry") is not None else None
                ),
            )
        )

    return results


@router.get("/api/positions/live", response_model=list[LivePositionResponse])
def get_positions_live() -> list[LivePositionResponse]:
    """Every open trade, marked at the price he would actually get right now.

    Polled every five seconds by the position area on the desk while the
    market is open, and by Home's band.

    TWO THINGS CHANGED HERE IN BUILD A, PART ONE.

    1. THE MARK IS THE SIDE HE WOULD GET, not the last traded price. A leg he
       bought is marked at the BID, because selling it is what he would do; a
       leg he sold is marked at the ASK, because buying it back is what he
       would do. The old code marked everything at the last trade, which is
       nobody's price, and then his "open profit" was a number he could not
       have realised. The exit fills this way already (`services/fills.py`,
       reversed), so the screen now agrees with the fill.

    2. ONE TRADE THE FEED CANNOT PRICE NO LONGER BLANKS THE PAGE. The chain
       fetch used to raise straight out of the loop, so a single position on
       an expiry FYERS would not serve took the whole reply down with it and
       the position area showed nothing at all. Each position is valued on
       its own now: one that cannot be priced comes back marked unavailable
       with the reason, and the others still show their figures.
    """
    positions_data: list[dict[str, Any]] = []

    try:
        client = db.client
        res = client.table("swayam_positions").select("*").eq("status", "open").execute()
        if res.data:
            positions_data.extend(res.data)
    except Exception as exc:
        logger.warning("Could not fetch positions from Supabase for live P&L: %s", exc)
        # If DB URL is configured but call failed, raise 503
        if db.url and db.key:
            raise HTTPException(status_code=503, detail="Cannot fetch positions from Supabase.") from exc

    # Same rule as above: the database owns the truth about a position, and a
    # stale in-memory copy on one instance must never resurrect a closed trade.
    existing_ids = {str(p.get("id")) for p in positions_data}
    local_ids = {str(l.get("id")) for l in _local_paper_positions} - existing_ids
    known = _ids_the_database_knows(local_ids)
    for local_pos in _local_paper_positions:
        pid = str(local_pos.get("id"))
        if pid in existing_ids or pid in known:
            continue
        if local_pos.get("status") == "open":
            positions_data.append(local_pos)

    if not positions_data:
        return []

    # THE ONE CLOCK. Nothing below may say live unless this says the market is
    # open, and this is the same function /api/market/data-health reads.
    market_state = "live" if _market_is_open_now() else "closing"
    read_at = datetime.now(timezone.utc).isoformat()

    # The balance is read once for the whole reply, not once per position, and
    # a balance that cannot be read makes rule 1 unavailable rather than
    # inventing a cap. Every figure is a percentage of the live balance.
    capital: Optional[Any] = None
    capital_reason: Optional[str] = None
    try:
        capital = capital_service.get_capital()
    except CapitalUnavailable as exc:
        capital_reason = str(exc)
    except Exception as exc:  # noqa: BLE001
        capital_reason = f"the account balance could not be read: {exc}"

    results: list[LivePositionResponse] = []
    for pos in positions_data:
        try:
            results.append(
                _value_one_position(
                    pos,
                    market_state=market_state,
                    read_at=read_at,
                    capital=capital,
                    capital_reason=capital_reason,
                )
            )
        except Exception as exc:  # noqa: BLE001
            # ONE BAD POSITION DOES NOT BLANK THE OTHERS. It comes back
            # unpriced, with the reason on it, and the card says so.
            detail = getattr(exc, "detail", None)
            reason = str(detail) if detail else str(exc)
            logger.warning(
                "Could not value position %s live: %s", str(pos.get("id"))[:8], reason
            )
            results.append(
                _unpriced_position(pos, reason=reason, market_state=market_state, read_at=read_at)
            )

    # BUILD B. What is WAITING on each of these trades, so Home's band can say
    # "2 resting" and the desk's card can too, without either of them counting
    # anything for itself. One read of the order book for the whole reply.
    _attach_resting_counts(results)
    return results


def _attach_resting_counts(results: list[LivePositionResponse]) -> None:
    """How many orders are waiting on each open trade, and the bell's warning.

    A failure here must never take the position area down: the money on the
    card is the point, and a missing count says so rather than raising.
    """
    if not results:
        return
    from swayam.services import orders as book

    try:
        rows = book.orders_for_day()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read the order book for the live positions: %s", exc)
        return

    resting: dict[str, int] = {}
    stranded: dict[str, list[str]] = {}
    for row in rows:
        position_id = str(row.get("position_id") or "")
        if not position_id:
            continue
        if row.get("status") in book.OPEN_STATES:
            resting[position_id] = resting.get(position_id, 0) + 1
        elif row.get("status") == book.EXPIRED and row.get("kind") in book.EXIT_KINDS:
            stranded.setdefault(position_id, []).append(book.leg_label(row.get("leg") or {}))

    for result in results:
        pid = str(result.position_id)
        result.resting_orders = resting.get(pid, 0)
        legs = stranded.get(pid)
        if legs:
            # HIS INSTRUCTION, 2026-09-10. A resting exit that the bell killed
            # leaves him holding a leg he meant to be out of, and he must not
            # discover that by accident.
            result.orders_warning = (
                f"You are NOT out of {', '.join(sorted(set(legs)))}. That exit never got your "
                f"price and expired at 15:30, so the leg is still yours. Check the 15:20 "
                f"naked-shorts reading before you carry it overnight."
            )


def _unpriced_position(
    pos: dict[str, Any],
    *,
    reason: str,
    market_state: str,
    read_at: str,
) -> LivePositionResponse:
    """A position the feed could not price, stated as such rather than as zero.

    Every money figure is None and `error` carries why. A partial sum shown as
    a whole one is the thing his first rule exists to stop.
    """
    legs = pos.get("legs") or []
    expiry_val = pos.get("expiry_date") or (legs[0].get("expiry_date") if legs else None)
    opened_at_str = str(pos.get("opened_at", datetime.now(timezone.utc).isoformat()))
    open_now = [l for l in legs if _leg_is_open(l)]
    return LivePositionResponse(
        position_id=str(pos.get("id")),
        strategy_name=str(pos.get("strategy_name") or "Options Strategy"),
        name_source=str(pos.get("name_source") or "structure"),
        underlying=str(pos.get("underlying") or "NIFTY"),
        opened_at=opened_at_str,
        expiry_date=str(expiry_val) if expiry_val else None,
        legs=[dict(l) for l in legs],
        entry_debit_credit_inr=float(pos.get("net_debit_credit_inr") or 0.0),
        max_loss_inr=_opt_float(pos.get("max_loss_inr")),
        max_loss_unbounded_reason=pos.get("max_loss_unbounded_reason"),
        max_profit_inr=float(pos.get("max_profit_inr") or 0.0),
        breakevens=list(pos.get("breakeven_points") or []),
        margin_required_inr=_opt_float(pos.get("margin_required_inr")),
        margin_source=pos.get("margin_source"),
        spot_at_entry=_opt_float(pos.get("spot_at_entry")),
        provenance=pos.get("provenance"),
        fill_basis=pos.get("fill_basis"),
        legs_open=len(open_now),
        legs_closed=len(legs) - len(open_now),
        days_held=_days_held(opened_at_str),
        days_remaining_to_expiry=_days_to_expiry(expiry_val),
        journal_path=pos.get("journal_path"),
        # A trade nobody could price is still a trade he holds, so the band
        # keeps its running state; there is simply nothing to compare a target
        # against, so `alerts` stays empty and `error` says why.
        state="running" if open_now else "quiet",
        market_state=market_state,
        read_at=read_at,
        error=reason,
    )


def _value_one_position(
    pos: dict[str, Any],
    *,
    market_state: str,
    read_at: str,
    capital: Optional[Any],
    capital_reason: Optional[str],
) -> LivePositionResponse:
    """One trade, marked leg by leg at the side he would get."""
    position_id = str(pos.get("id"))
    underlying = str(pos.get("underlying") or "NIFTY")
    opened_at_str = str(pos.get("opened_at", datetime.now(timezone.utc).isoformat()))
    all_legs: list[dict[str, Any]] = list(pos.get("legs") or [])
    entry_debit_credit = float(pos.get("net_debit_credit_inr") or 0.0)
    max_loss = _opt_float(pos.get("max_loss_inr"))
    max_loss_unbounded_reason = pos.get("max_loss_unbounded_reason")
    max_profit = float(pos.get("max_profit_inr") or 0.0)
    journal_path = pos.get("journal_path")

    # The name follows the open legs unless he named it himself. A row stored
    # before migration 022 has no name_source, which behaves like 'structure',
    # so his condor stops calling itself Short Strangle the moment it is read.
    name_source = str(pos.get("name_source") or "structure")
    strategy_name = resolve_name(
        all_legs, name_source=name_source, current_name=pos.get("strategy_name")
    )

    expiry_val = pos.get("expiry_date")
    if not expiry_val and all_legs:
        expiry_val = all_legs[0].get("expiry_date")

    raw_chain = _get_cached_option_chain(underlying, expiry=expiry_val)
    spot, chain_lookup = _build_chain_lookup(raw_chain)
    if spot <= 0.0:
        spot = fyers_client.get_nifty_spot()

    unrealized_pnl_total = 0.0
    current_position_value = 0.0
    charges_in_total = 0.0
    charges_out_total = 0.0
    # TWO DIFFERENT FAILURES, KEPT APART. A leg that cannot be marked makes
    # the PROFIT unknown. A leg with no recorded entry charge makes only the
    # COST of the round trip unknown, and the profit is still perfectly
    # readable. Every position opened before 2026-09-09 is in the second state.
    unpriced_reason: Optional[str] = None
    charges_reason: Optional[str] = None
    enriched_legs: list[dict[str, Any]] = []
    spread_legs: list[Leg] = []
    iv_map: dict[Leg, float] = {}
    greeks_unavailable_reason: Optional[str] = None
    legs_open = 0
    legs_closed = 0
    today = date.today()

    for leg in all_legs:
        leg_copy = dict(leg)

        # A CLOSED LEG KEEPS ITS OWN RESULT AND IS NOT RE-MARKED. It was
        # squared off at a real price on a real day; re-valuing it against
        # today's book would rewrite history.
        if not _leg_is_open(leg):
            legs_closed += 1
            leg_copy["status"] = "closed"
            leg_copy["mark"] = _opt_float(leg.get("exit_premium"))
            leg_copy["mark_side"] = leg.get("exit_side_hit")
            leg_copy["leg_pnl_inr"] = _opt_float(leg.get("gross_pnl_inr"))
            leg_copy["exit_charges_now_inr"] = _opt_float(leg.get("exit_charges_inr"))
            gross = _opt_float(leg.get("gross_pnl_inr"))
            entry_ch = _opt_float(leg.get("entry_charges_inr"))
            exit_ch = _opt_float(leg.get("exit_charges_inr"))
            if gross is None:
                unpriced_reason = (
                    unpriced_reason
                    or "a leg closed earlier has no recorded result, so the trade cannot be totalled"
                )
            else:
                unrealized_pnl_total += gross
            if entry_ch is None or exit_ch is None:
                charges_reason = charges_reason or (
                    "a leg closed earlier has no recorded charges"
                )
            else:
                charges_in_total += entry_ch
                charges_out_total += exit_ch
            enriched_legs.append(leg_copy)
            continue

        legs_open += 1
        leg_copy["status"] = "open"
        strike = float(leg.get("strike", 0.0))
        opt_type = str(leg.get("option_type", "CE")).upper()
        qty_lots = int(leg.get("quantity_lots", 1) or 1)

        # The contract size recorded when the position was opened. A stored
        # position must be valued at the size it was actually booked with, not
        # at today's contract master. Missing is an error, not a 75: the 67
        # legacy rows were booked at 75, which was never the real NIFTY lot,
        # and they are quarantined rather than re-valued.
        stored_lot = leg.get("lot_size")
        if not stored_lot:
            unpriced_reason = unpriced_reason or "a leg has no recorded contract size"
            leg_copy["error"] = "lot_size_missing_on_stored_leg"
            enriched_legs.append(leg_copy)
            continue
        lot_size = int(stored_lot)
        contracts = qty_lots * lot_size
        direction = str(leg.get("direction", "buy")).lower()
        is_buy = direction in ("buy", "long")
        entry_prem = float(leg.get("entry_premium", 0.0) or 0.0)

        quote = chain_lookup.get((strike, opt_type))
        if quote is None:
            unpriced_reason = unpriced_reason or "a leg is not in the current chain"
            leg_copy["error"] = "strike_not_in_current_chain"
            enriched_legs.append(leg_copy)
            continue

        # THE MARK IS THE SIDE HE WOULD GET. A bought leg is marked at the bid
        # because selling it is what closes it; a sold leg at the ask because
        # buying it back is what closes it. Exactly what services/fills.py
        # would do on the exit, so the screen and the fill agree.
        mark_side = "bid" if is_buy else "ask"
        mark = quote.get(mark_side)
        if mark is None:
            # No side of the book he could trade against. The last trade is
            # NOT a substitute; it is history and is shown as such.
            unpriced_reason = unpriced_reason or (
                f"the {mark_side} is not published for the {strike:,.0f} {opt_type}"
            )
            leg_copy["error"] = f"no_{mark_side}_published"
            leg_copy["current_ltp"] = quote.get("ltp")
            leg_copy["bid"] = quote.get("bid")
            leg_copy["ask"] = quote.get("ask")
            enriched_legs.append(leg_copy)
            continue

        mark = float(mark)
        leg_pnl = ((mark - entry_prem) * contracts) if is_buy else ((entry_prem - mark) * contracts)
        leg_val = (mark * contracts) if is_buy else (-mark * contracts)

        # What it would cost to get out of this leg right now, at this mark,
        # on the side it would actually hit. The only correct charge maths in
        # the repository, per leg, as he insisted.
        exit_charges_now: Optional[float] = None
        try:
            exit_charges_now = float(
                charge_for_leg(
                    side=opposite(side_from_direction(direction)),
                    price_per_unit=Decimal(str(mark)),
                    quantity_units=contracts,
                    on=today,
                ).total_inr
            )
        except ChargeScheduleUnavailable as exc:
            charges_reason = charges_reason or f"exit charges cannot be computed: {exc}"

        entry_charges = _opt_float(leg.get("entry_charges_inr"))
        if entry_charges is None:
            # Opened before charges were recorded per leg, on 2026-09-09. The
            # profit is still known; only what the round trip costs is not.
            charges_reason = charges_reason or (
                "a leg has no recorded entry charges, so the cost of the round trip is unknown"
            )
        else:
            charges_in_total += entry_charges
        if exit_charges_now is None:
            charges_reason = charges_reason or "an exit charge could not be computed"
        else:
            charges_out_total += exit_charges_now

        current_position_value += leg_val
        unrealized_pnl_total += leg_pnl

        leg_copy["mark"] = round(mark, 2)
        leg_copy["mark_side"] = mark_side
        leg_copy["leg_pnl_inr"] = round(leg_pnl, 2)
        leg_copy["exit_charges_now_inr"] = (
            round(exit_charges_now, 2) if exit_charges_now is not None else None
        )
        leg_copy["bid"] = quote.get("bid")
        leg_copy["ask"] = quote.get("ask")
        leg_copy["current_ltp"] = quote.get("ltp")
        leg_copy["current_iv"] = quote.get("iv")  # may be None: show "-", never 0.15
        leg_copy["current_value_inr"] = round(leg_val, 2)
        leg_copy["unrealized_pnl_inr"] = round(leg_pnl, 2)
        enriched_legs.append(leg_copy)

        # Build options_math Leg for Greeks
        try:
            exp_date = (
                datetime.fromisoformat(str(leg.get("expiry_date"))).date()
                if leg.get("expiry_date")
                else date.today()
            )
            # Leg carries no iv field; implied volatility belongs in the
            # iv_map. Passing iv= here raised TypeError on EVERY leg, and a
            # bare "except Exception: pass" swallowed it, so live position
            # greeks silently never worked at all. Fixed 2026-09-08.
            leg_iv = quote.get("iv")
            if leg_iv is None:
                greeks_unavailable_reason = (
                    "implied volatility is not published for at least one leg"
                )
                continue
            leg_obj = Leg(
                strike=strike,
                option_type=OptionType.CALL if opt_type == "CE" else OptionType.PUT,
                direction=Direction.BUY if is_buy else Direction.SELL,
                quantity_lots=qty_lots,
                lot_size=lot_size,
                entry_premium=entry_prem,
                expiry_date=exp_date,
            )
            spread_legs.append(leg_obj)
            iv_map[leg_obj] = float(leg_iv)
        except Exception as exc:
            # Never silent again. A leg that cannot be modelled makes the
            # greeks unavailable and says so.
            greeks_unavailable_reason = f"could not model a leg: {exc}"
            logger.warning("Position leg could not be modelled for greeks: %s", exc)

    live_greeks: Optional[LivePositionGreeks] = None
    if unpriced_reason is None and spread_legs and spot > 0:
        try:
            spread = Spread(name=strategy_name, underlying=underlying, legs=spread_legs)
            g_calc = compute_position_greeks(spread, spot, iv_map, as_of_date=date.today())
            live_greeks = LivePositionGreeks(
                net_delta=round(g_calc.net_delta, 4),
                net_gamma=round(g_calc.net_gamma, 6),
                net_theta_per_day=round(g_calc.net_theta_per_day, 2),
                net_vega=round(g_calc.net_vega, 2),
            )
        except Exception as e:
            greeks_unavailable_reason = f"greeks calculation failed: {e}"
            logger.warning("Failed to compute live greeks: %s", e)

    days_held = _days_held(opened_at_str)
    days_remaining = _days_to_expiry(expiry_val)

    # THE TOTALS, kept apart because two different things can be missing.
    if unpriced_reason is not None:
        # A leg could not be marked, so the profit itself is unknown. A sum
        # missing one leg is not a smaller profit, it is a wrong one.
        unrealized: Optional[float] = None
        position_value: Optional[float] = None
        unrealized_pct: Optional[float] = None
    else:
        unrealized = round(unrealized_pnl_total, 2)
        position_value = round(current_position_value, 2)
        unrealized_pct = round(unrealized / max_loss, 4) if max_loss > 0 else 0.0

    if unpriced_reason is not None or charges_reason is not None:
        # The profit may be known while the cost of the round trip is not.
        charges_in: Optional[float] = None
        charges_out: Optional[float] = None
        net_if_exit_now: Optional[float] = None
    else:
        charges_in = round(charges_in_total, 2)
        charges_out = round(charges_out_total, 2)
        # "the actual profit that will come into my account after exiting",
        # his words of 2026-09-10: gross, less what getting in cost, less what
        # getting out would cost at these marks.
        net_if_exit_now = round(unrealized_pnl_total - charges_in_total - charges_out_total, 2)

    # Rule 1: the running loss against 1% of the balance read fresh this
    # session. Headroom is what is left before it bites. A profit uses none of
    # it. No balance, no cap, and it says why.
    rule1_cap: Optional[float] = None
    rule1_headroom: Optional[float] = None
    rule4_ceiling: Optional[float] = None
    rule_reason = capital_reason
    if capital is not None:
        rule1_cap = capital.primary_risk_cap_inr
        rule4_ceiling = capital.deployable_margin_ceiling_inr
        if rule4_ceiling is None:
            rule_reason = rule_reason or capital.ceiling_unavailable_reason
        # Rule 1 is measured against what he would actually be left with. If
        # the charges cannot be read, the running loss falls back to the gross,
        # which understates it slightly and is stated as such rather than
        # skipped: a headroom he cannot see is worse than a cautious one.
        running_basis = net_if_exit_now if net_if_exit_now is not None else unrealized
        if running_basis is not None:
            running_loss = max(0.0, -running_basis)
            rule1_headroom = round(max(0.0, rule1_cap - running_loss), 2)

    # TARGETS, and whether one has been reached. Evaluated against the same
    # marks every other figure on this reply came from, so the signal and the
    # money agree. A leg is judged on its price, the trade on its net after
    # charges both ways, and a blank trade loss falls back to rule 1's cap read
    # live above. Nothing here exits anything.
    verdict = evaluate_targets(
        legs=enriched_legs,
        net_if_exit_now_inr=net_if_exit_now,
        target_profit_inr=_opt_float(pos.get("target_profit_inr")),
        target_loss_inr=_opt_float(pos.get("target_loss_inr")),
        targets_set_at=(str(pos["targets_set_at"]) if pos.get("targets_set_at") else None),
        rule1_cap_inr=rule1_cap,
        legs_open=legs_open,
        market_state=market_state,
    )

    return LivePositionResponse(
        position_id=position_id,
        strategy_name=strategy_name,
        name_source=name_source,
        underlying=underlying,
        opened_at=opened_at_str,
        expiry_date=str(expiry_val) if expiry_val else None,
        legs=enriched_legs,
        entry_debit_credit_inr=entry_debit_credit,
        max_loss_inr=max_loss,
        max_loss_unbounded_reason=max_loss_unbounded_reason,
        max_profit_inr=max_profit,
        breakevens=list(pos.get("breakeven_points") or []),
        current_spot=spot,
        spot_at_entry=_opt_float(pos.get("spot_at_entry")),
        current_position_value_inr=position_value,
        unrealized_pnl_inr=unrealized,
        unrealized_pnl_pct_of_risk=unrealized_pct,
        charges_in_inr=charges_in,
        charges_out_now_inr=charges_out,
        net_if_exit_now_inr=net_if_exit_now,
        rule1_cap_inr=rule1_cap,
        rule1_headroom_inr=rule1_headroom,
        rule4_ceiling_inr=rule4_ceiling,
        rules_unavailable_reason=rule_reason,
        margin_required_inr=_opt_float(pos.get("margin_required_inr")),
        margin_source=pos.get("margin_source"),
        provenance=pos.get("provenance"),
        fill_basis=pos.get("fill_basis"),
        legs_open=legs_open,
        legs_closed=legs_closed,
        current_greeks=live_greeks,
        greeks_unavailable_reason=(
            None if live_greeks else (greeks_unavailable_reason or "greeks not computed")
        ),
        days_held=days_held,
        days_remaining_to_expiry=days_remaining,
        journal_path=journal_path,
        state=verdict["state"],
        alerts=verdict["alerts"],
        targets=verdict["targets"],
        market_state=market_state,
        read_at=read_at,
        error=unpriced_reason,
        charges_unavailable_reason=charges_reason,
    )


def _resolve_journal_path(pos: dict[str, Any], position_id: str) -> Optional[str]:
    """Where this trade's note lives in his vault, or nothing at all.

    The path was only ever kept in an in-memory dict at entry, so the position
    row did not carry it and the exit block was never appended. It is stored on
    the row from 2026-09-09, and any row written before that is recovered from
    `swayam_journal_entries.md_path`, where it was always recorded.

    Returns None when there genuinely is no note, which happens when the vault
    was unreachable and the note is sitting in the outbox. That is a real state,
    not an error, and the close must still succeed.
    """
    stored = pos.get("journal_path")
    if stored:
        return str(stored)

    try:
        res = (
            db.client.table("swayam_journal_entries")
            .select("md_path")
            .eq("position_id", position_id)
            .eq("entry_type", "entry")
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if rows and rows[0].get("md_path"):
            return str(rows[0]["md_path"])
    except Exception as exc:
        logger.warning("Could not look up the note path for %s: %s", position_id, exc)

    return None


def _legs_that_would_rest(
    legs: list[dict[str, Any]],
    exit_legs: Optional[list[CloseLegItem]],
    chain_lookup: dict[tuple[float, str], dict[str, Any]],
    market_open: bool,
    supplied_only: bool,
) -> list[dict[str, Any]]:
    """Which legs of this Exit everything are waiting on HIS PRICE.

    Decided on the chain that has already been read, so it costs nothing extra
    and happens before a single leg is touched.

    A price he SUPPLIED himself is not an order and never rests: it is his
    instruction from a terminal and is recorded as supplied. After the bell
    nothing rests either, and the close keeps its own words about the market
    being shut.
    """
    if supplied_only or not market_open or not exit_legs:
        return []

    waiting: list[dict[str, Any]] = []
    for leg in legs:
        if not _leg_is_open(leg):
            continue
        strike = float(leg.get("strike", 0.0))
        opt_type = str(leg.get("option_type", "CE")).upper()
        instruction = None
        for el in exit_legs:
            if abs(float(el.strike) - strike) < 0.01 and el.option_type.upper() == opt_type:
                instruction = el
                break
        if instruction is None or instruction.is_supplied:
            continue
        if str(instruction.order_type or "MARKET").upper() != "LIMIT":
            continue
        limit = _opt_float(instruction.limit_price)
        if limit is None or limit <= 0:
            continue

        exit_direction = exit_side_of(str(leg.get("direction", "buy")).lower())
        quote_row = chain_lookup.get((strike, opt_type)) or {}
        quote = LegQuote(
            ltp=quote_row.get("ltp"), bid=quote_row.get("bid"), ask=quote_row.get("ask"),
            spot=None, state="live", market_open=True, as_of=None,
        )
        side_price = quote.ask if exit_direction == "buy" else quote.bid
        if not is_his_price(
            order_type="LIMIT",
            book_is_tradeable=quote.tradeable,
            side_price=side_price,
            limit_price=limit,
        ):
            continue
        # The book IS there and it has simply not come to his number. Would it
        # fill right now? If it would, it is not waiting for anything.
        marketable = (limit >= side_price) if exit_direction == "buy" else (limit <= side_price)
        if marketable:
            continue
        waiting.append({
            "sequence": int(leg.get("sequence") or 0),
            "leg": leg,
            "limit_price": float(limit),
            "book": side_price,
            "side": "ask" if exit_direction == "buy" else "bid",
            "label": f"{exit_direction.upper()} {strike:,.0f} {opt_type}",
        })
    return waiting


def _close_some_and_rest_the_others(
    *,
    position_id: str,
    pos: dict[str, Any],
    legs: list[dict[str, Any]],
    req: ClosePositionRequest,
    waiting: list[dict[str, Any]],
) -> dict[str, Any]:
    """Exit everything, when some of it has to wait for his price.

    The legs that can fill go out ONE AT A TIME through the per-leg exit that
    Build A built, so each one gets its own fill, its own charges, its own
    line on the note and its own place in the campaign. The legs that cannot
    fill become open orders. The trade stays open behind them, and the single
    result row is written by the same code as always, when the last open leg
    finally closes.

    Nothing here re-implements a close. It presses the buttons that exist.
    """
    from swayam.api.routes.execution import (
        ExitLegRequest,
        _rest_them,
        _exit_leg_request,
        exit_one_leg,
    )
    from swayam.services import orders as book

    underlying = str(pos.get("underlying") or "NIFTY")
    group_id = str(uuid.uuid4())
    waiting_sequences = {int(w["sequence"]) for w in waiting}

    # The orders first, so that if the book cannot be written NOTHING has been
    # exited and he is exactly where he started.
    resting = _rest_them(
        [
            {
                "sequence": w["sequence"],
                "leg": _exit_leg_request(w["leg"], pos),
                "label": w["label"],
                "limit_price": w["limit_price"],
                "book": w["book"],
                "side": w["side"],
            }
            for w in waiting
        ],
        underlying=underlying,
        strategy_name=pos.get("strategy_name"),
        kind=book.EXIT_ALL_LEG,
        position_id=position_id,
        group_id=group_id,
    )

    exited: list[dict[str, Any]] = []
    could_not: list[dict[str, Any]] = []
    for leg in legs:
        if not _leg_is_open(leg):
            continue
        sequence = int(leg.get("sequence") or 0)
        if sequence in waiting_sequences:
            continue
        instruction = None
        for el in (req.exit_legs or []):
            if (abs(float(el.strike) - float(leg.get("strike", 0.0))) < 0.01
                    and el.option_type.upper() == str(leg.get("option_type", "")).upper()):
                instruction = el
                break
        try:
            result = exit_one_leg(position_id, sequence, ExitLegRequest(
                order_type=str((instruction.order_type if instruction else "MARKET") or "MARKET").upper(),
                limit_price=(_opt_float(instruction.limit_price) if instruction else None),
                close_reason=req.close_reason,
                notes=req.notes,
            ))
            exited.append(result)
        except HTTPException as exc:
            detail = exc.detail
            refused = detail.get("refused_legs") if isinstance(detail, dict) else None
            could_not.append({
                "leg": f"{float(leg.get('strike', 0)):,.0f} {str(leg.get('option_type', '')).upper()}",
                "reason": str(
                    (refused[0].get("reason") if refused else None)
                    or (detail.get("error") if isinstance(detail, dict) else detail)
                ),
            })

    still_open = sum(
        1 for leg in _reread_legs(position_id, legs) if _leg_is_open(leg)
    )
    return {
        "position_id": position_id,
        "status": "partially_exited",
        "trade_closed": still_open == 0,
        "exited": exited,
        "exited_count": len(exited),
        "resting": resting,
        "resting_count": len(resting),
        "could_not_exit": could_not,
        "legs_open": still_open,
        "message": (
            f"{len(exited)} leg{'' if len(exited) == 1 else 's'} exited. "
            + (f"{len(resting)} order{'' if len(resting) == 1 else 's'} now waiting for your price; "
               f"{'it expires' if len(resting) == 1 else 'they expire'} at 15:30 and the trade stays "
               f"open behind {'it' if len(resting) == 1 else 'them'}. ")
            + ("You are NOT out of this trade yet." if still_open else "")
        ).strip(),
    }


def _reread_legs(position_id: str, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The trade's legs as they stand now, after the per-leg exits above."""
    try:
        res = db.client.table("swayam_positions").select("legs").eq("id", position_id).execute()
        rows = getattr(res, "data", None) or []
        if rows and isinstance(rows[0].get("legs"), list):
            return rows[0]["legs"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not re-read the legs of %s: %s", position_id, exc)
    return fallback


# The response model is declared on ClosePositionResponse and still returned
# for every close that actually closes. It is NOT declared on the decorator
# since Build B, because an Exit everything where some legs rest does not
# close the trade and has no result row: it answers with what filled, what is
# waiting and what is still open. Forcing that through a model whose
# realized_pnl_inr is a required float would mean inventing a zero for a trade
# that has not finished, which is exactly the kind of number he has banned.
@router.post("/api/positions/{position_id}/close")
def close_position(position_id: str, req: ClosePositionRequest) -> Any:
    """Closes an open position with Database-before-Journal ordering.

    1. Validates position exists and status is 'open'.
    2. Computes realized P&L and estimated transaction costs.
    3. INSERTS to `swayam_trade_history`.
    4. UPDATES `swayam_positions` SET status = 'closed'.
    5. Appends the exit report to the Obsidian journal file.
    """
    # 1. Fetch position
    pos: Optional[dict[str, Any]] = None

    try:
        res = db.client.table("swayam_positions").select("*").eq("id", position_id).execute()
        if res.data:
            pos = res.data[0]
    except Exception as exc:
        logger.warning("Error fetching position %s from Supabase: %s", position_id, exc)

    if pos is None:
        for local_pos in _local_paper_positions:
            if str(local_pos.get("id")) == position_id:
                pos = local_pos
                break

    if pos is None:
        raise HTTPException(status_code=404, detail=f"Position '{position_id}' not found.")

    if pos.get("status") != "open":
        raise HTTPException(status_code=400, detail="Position already closed.")

    legs = pos.get("legs", [])
    entry_debit_credit = float(pos.get("net_debit_credit_inr", 0.0))
    # A NAKED TRADE HAS NO MAXIMUM LOSS, and the column now holds NULL for it.
    # `float(pos.get("max_loss_inr", 0.0))` looked safe and was not: the KEY is
    # present, so the 0.0 default never fired, and `float(None)` raised. Closing
    # a naked trade through this route failed outright. Found by the review of
    # Round 1b, 2026-09-11, on a path nobody had run.
    max_loss = _opt_float(pos.get("max_loss_inr"))
    journal_path = _resolve_journal_path(pos, position_id)
    underlying = pos.get("underlying", "NIFTY")
    expiry_val = pos.get("expiry_date") or (legs[0].get("expiry_date") if legs else None)

    # 2. Resolve exit premiums per leg.
    #
    # A ticket may now send an order type and a limit price for EACH leg, so
    # the book is needed unless every single leg came with a price he supplied
    # himself. A supplied price still bypasses the book, and still bypasses
    # the clock, because it is his instruction and not a fill.
    supplied_only = bool(req.exit_legs) and all(el.is_supplied for el in req.exit_legs)
    chain_lookup: dict[tuple[float, str], dict[str, Any]] = {}
    spot_at_exit: Optional[float] = None
    if not supplied_only:
        raw_chain = _get_cached_option_chain(underlying, expiry=expiry_val)
        spot_val, chain_lookup = _build_chain_lookup(raw_chain)
        if spot_val > 0:
            spot_at_exit = spot_val

    # Both dates are needed inside the leg loop: an exit is charged on today's
    # schedule and an entry on the schedule in force the day it opened. Rates
    # change, and a trade carried across 1 April 2026 straddles two of them.
    closed_at = datetime.now(timezone.utc)
    opened_at_str = str(pos.get("opened_at", closed_at.isoformat()))
    try:
        opened_at_dt = datetime.fromisoformat(opened_at_str.replace("Z", "+00:00"))
        holding_days = max(0, (closed_at.date() - opened_at_dt.date()).days)
        time_in_trade_minutes = max(0, int((closed_at - opened_at_dt).total_seconds() / 60))
    except Exception:
        opened_at_dt = closed_at
        holding_days = 0
        time_in_trade_minutes = None

    # BUILD B. BEFORE ANY LEG IS TOUCHED: which of them are waiting on HIS
    # PRICE rather than on the market.
    #
    # An Exit everything where one leg's limit is away from the book used to
    # refuse the whole close. It now fills what it can and rests the rest, so
    # he can walk out of three legs of a condor at market and hold out for a
    # price on the fourth. The trade stays open behind the leg that waits, and
    # ONE result row is written only when the last open leg actually closes.
    #
    # This runs first, on the chain that has already been read, so it costs no
    # extra call and nothing is half done: either the whole close proceeds as
    # it always has, or it is handed over to the per-leg path below.
    market_open = _market_is_open_now() if not supplied_only else True
    would_rest = _legs_that_would_rest(legs, req.exit_legs, chain_lookup, market_open, supplied_only)
    if would_rest:
        return _close_some_and_rest_the_others(
            position_id=position_id,
            pos=pos,
            legs=legs,
            req=req,
            waiting=would_rest,
        )

    gross_exit_value = 0.0
    total_entry_charges = 0.0
    total_exit_charges = 0.0
    closed_legs: list[dict[str, Any]] = []
    # Every leg as it will be stored back on the row, carrying its own closed
    # state. A trade is a campaign: this is where each leg's own result lives.
    legs_after: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []

    for leg in legs:
        # A LEG ALREADY SQUARED OFF IS NOT FILLED AGAIN. His rule of
        # 2026-09-08: "Every leg that I square off will have its own
        # profit/loss added." That leg made its result on the day it was
        # closed, at a price that was real then; it contributes those figures
        # to the one result row and is not re-marked against today's book.
        if not _leg_is_open(leg):
            stored = dict(leg)
            gross = _opt_float(stored.get("gross_pnl_inr"))
            entry_ch = _opt_float(stored.get("entry_charges_inr"))
            exit_ch = _opt_float(stored.get("exit_charges_inr"))
            if gross is None or entry_ch is None or exit_ch is None:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"The {float(stored.get('strike', 0)):,.0f} "
                        f"{str(stored.get('option_type', '')).upper()} leg was closed earlier "
                        "but has no recorded result, so this trade cannot be totalled. "
                        "It needs reconciling rather than guessing."
                    ),
                )
            gross_exit_value += gross
            total_entry_charges += entry_ch
            total_exit_charges += exit_ch
            closed_legs.append({
                "strike": float(stored.get("strike", 0.0)),
                "option_type": str(stored.get("option_type", "")).upper(),
                "direction": str(stored.get("direction", "")),
                "quantity_lots": int(stored.get("quantity_lots", 1) or 1),
                "lot_size": stored.get("lot_size"),
                "entry_premium": _opt_float(stored.get("entry_premium")),
                "exit_premium": _opt_float(stored.get("exit_premium")),
                "exit_order_type": stored.get("exit_order_type"),
                "exit_fill_basis": stored.get("exit_fill_basis"),
                "exit_side_hit": stored.get("exit_side_hit"),
                "exit_ltp": _opt_float(stored.get("exit_ltp")),
                "exit_how": stored.get("exit_how"),
                "exit_spread_cost_inr": _opt_float(stored.get("exit_spread_cost_inr")),
                "gross_pnl_inr": round(gross, 2),
                "entry_charges_inr": round(entry_ch, 2),
                "exit_charges_inr": round(exit_ch, 2),
                "charges_inr": round(entry_ch + exit_ch, 2),
                "net_pnl_inr": round(gross - entry_ch - exit_ch, 2),
                "closed_earlier_at": stored.get("closed_at"),
                "entry_charges_source": stored.get("entry_charges_source") or "recorded when the leg was opened",
            })
            legs_after.append(stored)
            continue

        strike = float(leg.get("strike", 0.0))
        opt_type = str(leg.get("option_type", "CE")).upper()
        qty_lots = int(leg.get("quantity_lots", 1) or 1)
        # As above: the size the position was booked with, never a default.
        stored_lot = leg.get("lot_size")
        if not stored_lot:
            raise HTTPException(
                status_code=422,
                detail=(
                    "This position has a leg with no recorded contract size, so it "
                    "cannot be valued. It needs reconciling rather than guessing."
                ),
            )
        lot_size = int(stored_lot)
        contracts = qty_lots * lot_size
        direction = str(leg.get("direction", "buy")).lower()
        is_buy = direction in ("buy", "long")

        exit_prem: Optional[float] = None
        exit_how = "supplied"
        exit_side_hit = ""
        exit_ltp: Optional[float] = None
        exit_basis = "supplied"
        exit_direction = exit_side_of(direction)
        leg_label = f"{exit_direction.upper()} {strike:,.0f} {opt_type}"

        # Which instruction, if any, this leg was given.
        instruction = None
        if req.exit_legs:
            for el in req.exit_legs:
                if abs(float(el.strike) - strike) < 0.01 and el.option_type.upper() == opt_type:
                    instruction = el
                    break
            if instruction is None:
                refused.append({"leg": leg_label, "reason": f"{leg_label}: no exit price was supplied for this leg."})
                continue

        exit_order_type = "MARKET"
        exit_limit_price: Optional[float] = None

        if instruction is not None and instruction.is_supplied:
            # An explicit price is his instruction, from a terminal or a
            # script. Recorded as supplied, never dressed up as a market fill.
            exit_prem = float(instruction.exit_premium)
            exit_order_type = "SUPPLIED"
        else:
            # THE EXIT FILLS THE WAY THE ENTRY DOES, REVERSED. A bought leg is
            # sold at the bid, a sold leg is bought back at the ask, from the
            # book right now, and only while the market is open. It used to
            # value every exit at the last traded price at any hour.
            #
            # Each leg may carry its own order type and limit price now, so he
            # can walk out of a condor at market on three legs and hold out
            # for a price on the fourth.
            if instruction is not None and instruction.order_type:
                exit_order_type = str(instruction.order_type).upper()
                exit_limit_price = (
                    float(instruction.limit_price) if instruction.limit_price is not None else None
                )
            q = chain_lookup.get((strike, opt_type)) or {}
            quote = LegQuote(
                ltp=q.get("ltp"), bid=q.get("bid"), ask=q.get("ask"), spot=spot_at_exit,
                state="live" if market_open else "closing", market_open=market_open, as_of=None,
            )
            side_needed_price = quote.ask if exit_direction == "buy" else quote.bid
            try:
                fill = resolve_fill(
                    direction=exit_direction, order_type=exit_order_type,
                    limit_price=exit_limit_price, quote=quote, leg_label=leg_label,
                )
            except FillRefused as exc:
                # A price he chose and a rule he broke must never read alike.
                refused.append({
                    "leg": leg_label,
                    "reason": reword_if_his_price(
                        str(exc),
                        direction=exit_direction,
                        order_type=exit_order_type,
                        book_is_tradeable=quote.tradeable,
                        side_price=side_needed_price,
                        limit_price=exit_limit_price,
                    ),
                    "market": exc.market,
                    "your_price": exit_limit_price,
                })
                continue
            exit_prem = fill.price
            exit_how = fill.how
            exit_side_hit = fill.side_hit
            exit_ltp = fill.ltp_at_fill
            exit_basis = fill.basis
            exit_order_type = fill.order_type
            exit_limit_price = fill.limit_price

        entry_prem = float(leg.get("entry_premium", 0.0) or 0.0)
        leg_pnl = ((exit_prem - entry_prem) * contracts) if is_buy else ((entry_prem - exit_prem) * contracts)
        gross_exit_value += leg_pnl

        # THE CHARGE BELONGS TO THE LEG, ON ITS OWN SIDE, AT ITS OWN PRICE.
        #
        # His instruction, 2026-09-09: "Charges are recorded as per the leg. The
        # buy leg has its own charges, and the sell leg has its own charges. Why
        # would squaring one leg charge for the whole trade?"
        #
        # This replaces a flat Rs 150 multiplied by the number of legs, applied
        # once at the close, with nothing charged at entry at all. On a one-lot
        # condor that guess was Rs 600 against a real Rs 223 round trip.
        #
        # Costing legs one at a time is exact, not an approximation: brokerage
        # is per order and every other line is a percentage of that leg's own
        # turnover, so the per-leg costs sum to the same paisa as costing the
        # whole side together. tests/test_charges_per_leg.py asserts it.
        entry_side = side_from_direction(direction)
        try:
            exit_cost = charge_for_leg(
                side=opposite(entry_side),
                price_per_unit=Decimal(str(exit_prem)),
                quantity_units=contracts,
                on=closed_at.date(),
            )
        except ChargeScheduleUnavailable as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Cannot close this position: the {strike:.0f} {opt_type} leg "
                    f"cannot be charged, so its result would be unknown. {exc}"
                ),
            ) from exc

        # What getting in cost. Recorded on the leg since 2026-09-09; for a
        # position opened before that, rebuilt from the real schedule in force
        # on the day it opened. Rebuilt is not invented, and it says which.
        recorded_entry = leg.get("entry_charges_inr")
        if recorded_entry is None:
            entry_cost_inr = float(
                charge_for_leg(
                    side=entry_side,
                    price_per_unit=Decimal(str(entry_prem)),
                    quantity_units=contracts,
                    on=opened_at_dt.date(),
                ).total_inr
            )
            entry_charges_source = "rebuilt from the schedule in force at entry"
        else:
            entry_cost_inr = float(recorded_entry)
            entry_charges_source = "recorded when the leg was opened"

        exit_cost_inr = float(exit_cost.total_inr)
        leg_charges = round(entry_cost_inr + exit_cost_inr, 2)
        total_entry_charges += entry_cost_inr
        total_exit_charges += exit_cost_inr

        leg_result = {
            "strike": strike,
            "option_type": opt_type,
            "direction": direction,
            "quantity_lots": qty_lots,
            "lot_size": lot_size,
            "entry_premium": entry_prem,
            "exit_premium": exit_prem,
            "exit_order_type": exit_order_type,
            "exit_limit_price": exit_limit_price,
            "exit_fill_basis": exit_basis,
            "exit_side_hit": exit_side_hit,
            "exit_ltp": exit_ltp,
            "exit_how": exit_how,
            "exit_spread_cost_inr": spread_cost_inr(exit_direction, exit_prem, exit_ltp, contracts),
            # Per leg, the three figures he asked for.
            "gross_pnl_inr": round(leg_pnl, 2),
            "entry_charges_inr": round(entry_cost_inr, 2),
            "exit_charges_inr": round(exit_cost_inr, 2),
            "charges_inr": leg_charges,
            "net_pnl_inr": round(leg_pnl - leg_charges, 2),
            "entry_charges_source": entry_charges_source,
            "charges_schedule_version": exit_cost.schedule_version,
        }
        closed_legs.append(leg_result)

        # THE LEG CARRIES ITS OWN STATE ON THE ROW. Everything the leg was
        # keeps its place; the exit is added beside it. This is what lets a
        # trade hold legs that closed on different days, which is how he has
        # always traded: his own sheet has "Booked Orders / Exits" on rows
        # dated apart from the entry.
        legs_after.append({
            **dict(leg),
            "status": "closed",
            "closed_at": closed_at.isoformat(),
            "exit_premium": exit_prem,
            "exit_side_hit": exit_side_hit,
            "exit_ltp": exit_ltp,
            "exit_order_type": exit_order_type,
            "exit_limit_price": exit_limit_price,
            "exit_fill_basis": exit_basis,
            "exit_how": exit_how,
            "exit_spread_cost_inr": leg_result["exit_spread_cost_inr"],
            "exit_charges_inr": round(exit_cost_inr, 2),
            "entry_charges_inr": round(entry_cost_inr, 2),
            "gross_pnl_inr": round(leg_pnl, 2),
            "net_pnl_inr": round(leg_pnl - leg_charges, 2),
        })

    # One leg that cannot be filled refuses the whole close. Nothing is written,
    # the position stays open, and every leg is named with what to do. The
    # commonest reason is the bell: after 15:30 nothing can fill, and the
    # answer says so rather than valuing his exit at a price nobody could get.
    if refused:
        raise HTTPException(
            status_code=422,
            detail={
                "error": (
                    "Not closed. "
                    + ("One leg" if len(refused) == 1 else f"{len(refused)} legs")
                    + " could not be filled honestly; every leg is listed below with what to do. "
                    + ("The market is closed; close it in your window." if not market_open else "")
                ).strip(),
                "refused_legs": refused,
            },
        )

    # 3. THE RESULT. One trade, one row, written in one place.
    #
    # This used to live inline here. It moved into `close_trade_from_legs`
    # when a leg gained the ability to close on its own, because the last leg
    # to close ALSO closes the trade, and two functions writing one result row
    # is precisely how a trade was recorded twice on 2026-09-09.
    return close_trade_from_legs(
        position_id=position_id,
        pos=pos,
        legs_after=legs_after,
        closed_legs=closed_legs,
        closed_at=closed_at,
        close_reason=req.close_reason,
        notes=req.notes,
        gross_total=gross_exit_value,
        total_entry_charges=total_entry_charges,
        total_exit_charges=total_exit_charges,
        spot_at_exit=spot_at_exit,
        journal_path=journal_path,
        max_loss=max_loss,
        holding_days=holding_days,
        time_in_trade_minutes=time_in_trade_minutes,
    )


def close_trade_from_legs(
    *,
    position_id: str,
    pos: dict[str, Any],
    legs_after: list[dict[str, Any]],
    closed_at: datetime,
    close_reason: str = "manual",
    notes: Optional[str] = None,
    closed_legs: Optional[list[dict[str, Any]]] = None,
    gross_total: Optional[float] = None,
    total_entry_charges: Optional[float] = None,
    total_exit_charges: Optional[float] = None,
    spot_at_exit: Optional[float] = None,
    journal_path: Optional[str] = None,
    max_loss: Optional[float] = None,
    holding_days: Optional[int] = None,
    time_in_trade_minutes: Optional[int] = None,
) -> Any:
    """Writes the ONE result row for a trade whose every leg is now closed.

    Two callers: the whole-trade close, which has just filled every leg, and
    the single-leg exit, when the leg it closed was the last one open. His
    rule: "Once I close all the legs or I say 'the trade is closed', then
    only the trade is closed." Everything a leg made or lost, on whatever day
    it was squared off, is summed here.

    A caller that has already done the arithmetic passes it in. A caller that
    has not, which is the last-leg case, leaves it out and it is read off the
    legs themselves, where every leg records its own result.
    """
    # Whatever the caller did not work out is read off the legs. Each leg
    # carries its own gross and its own charges both ways, so the trade's
    # figures are the sums and nothing is estimated.
    if closed_legs is None:
        closed_legs = []
        for leg in legs_after:
            closed_legs.append({
                "strike": _opt_float(leg.get("strike")),
                "option_type": str(leg.get("option_type", "")).upper(),
                "direction": str(leg.get("direction", "")),
                "quantity_lots": int(leg.get("quantity_lots", 1) or 1),
                "lot_size": leg.get("lot_size"),
                "entry_premium": _opt_float(leg.get("entry_premium")),
                "exit_premium": _opt_float(leg.get("exit_premium")),
                "exit_order_type": leg.get("exit_order_type"),
                "exit_limit_price": _opt_float(leg.get("exit_limit_price")),
                "exit_fill_basis": leg.get("exit_fill_basis"),
                "exit_side_hit": leg.get("exit_side_hit"),
                "exit_ltp": _opt_float(leg.get("exit_ltp")),
                "exit_how": leg.get("exit_how"),
                "exit_spread_cost_inr": _opt_float(leg.get("exit_spread_cost_inr")),
                "gross_pnl_inr": _opt_float(leg.get("gross_pnl_inr")),
                "entry_charges_inr": _opt_float(leg.get("entry_charges_inr")),
                "exit_charges_inr": _opt_float(leg.get("exit_charges_inr")),
                "charges_inr": round(
                    float(leg.get("entry_charges_inr") or 0.0) + float(leg.get("exit_charges_inr") or 0.0), 2
                ),
                "net_pnl_inr": _opt_float(leg.get("net_pnl_inr")),
                "closed_earlier_at": leg.get("closed_at"),
                "entry_charges_source": leg.get("entry_charges_source"),
            })

    missing = [
        f"{float(l.get('strike') or 0):,.0f} {l.get('option_type')}"
        for l in closed_legs
        if l.get("gross_pnl_inr") is None
        or l.get("entry_charges_inr") is None
        or l.get("exit_charges_inr") is None
    ]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=(
                "This trade cannot be totalled because "
                + ", ".join(missing)
                + " has no recorded result. It needs reconciling rather than guessing."
            ),
        )

    if gross_total is None:
        gross_total = sum(float(l["gross_pnl_inr"]) for l in closed_legs)
    if total_entry_charges is None:
        total_entry_charges = sum(float(l["entry_charges_inr"]) for l in closed_legs)
    if total_exit_charges is None:
        total_exit_charges = sum(float(l["exit_charges_inr"]) for l in closed_legs)
    if journal_path is None:
        journal_path = _resolve_journal_path(pos, position_id)
    if max_loss is None:
        # `or 0.0` did not crash; it handed a zero to the exit note, which then
        # printed the result as a percentage of a risk of nothing. The absence
        # travels all the way to the note now, which says the risk had no
        # ceiling instead of inventing a denominator.
        max_loss = _opt_float(pos.get("max_loss_inr"))
    opened_at_str = str(pos.get("opened_at", closed_at.isoformat()))
    if holding_days is None or time_in_trade_minutes is None:
        try:
            opened_at_dt = datetime.fromisoformat(opened_at_str.replace("Z", "+00:00"))
            holding_days = max(0, (closed_at.date() - opened_at_dt.date()).days)
            time_in_trade_minutes = max(0, int((closed_at - opened_at_dt).total_seconds() / 60))
        except Exception:
            holding_days = 0
            time_in_trade_minutes = None

    # 3. Compute Realized P&L and Estimated Charges
    # The trade's three figures, each the sum of its legs': cumulative gross,
    # cumulative charges for the whole round trip, and the net after them.
    gross_pnl_inr = round(gross_total, 2)
    total_charges_inr = round(total_entry_charges + total_exit_charges, 2)
    realized_pnl_inr = round(gross_pnl_inr - total_charges_inr, 2)

    spot_at_entry = float(pos.get("spot_at_entry") or 0.0) if pos.get("spot_at_entry") else None
    points_in_trade = round(spot_at_exit - spot_at_entry, 2) if (spot_at_exit and spot_at_entry) else None
    outcome = "WIN" if realized_pnl_inr > 0 else "LOSS" if realized_pnl_inr < 0 else "BREAKEVEN"

    # 4. Database-before-journal ordering
    # Step A: Insert to swayam_trade_history
    trade_history_record = {
        "position_id": position_id,
        "closed_at": closed_at.isoformat(),
        "close_reason": close_reason,
        "realized_pnl_inr": realized_pnl_inr,
        "total_charges_inr": total_charges_inr,
        "holding_days": holding_days,
        "exit_legs": closed_legs,
        "journal_md_path": journal_path,
    }

    # ONE CLOSE, ONE RESULT.
    #
    # Until 2026-09-09 the UPDATE below failed on a column that did not exist,
    # so the position stayed `open` after its result had already been written.
    # Pressing close again passed the "already closed" check and wrote a SECOND
    # result row, double counting the trade in his record. The migration adds a
    # unique index; this is the same rule in code, so the retry heals the
    # half-finished close instead of duplicating it.
    already_recorded = False
    try:
        prior = (
            db.client.table("swayam_trade_history")
            .select("id")
            .eq("position_id", position_id)
            .limit(1)
            .execute()
        )
        already_recorded = bool(prior.data)
    except Exception as exc:
        logger.warning(
            "Could not check for an existing result on %s: %s", position_id, exc
        )

    if already_recorded:
        logger.info(
            "Position %s already has a recorded result; completing the close "
            "rather than writing a second one.",
            position_id,
        )

    try:
        if not already_recorded:
            db.client.table("swayam_trade_history").insert(trade_history_record).execute()
    except Exception as exc:
        logger.error("Database insert to swayam_trade_history failed for %s: %s", position_id, exc)
        if db.url and db.key:
            raise HTTPException(
                status_code=503,
                detail=f"Database error writing trade history: {exc}",
            ) from exc

    # Step B: Update swayam_positions status to 'closed' and record trade journal metrics
    pos_update_payload = {
        "status": "closed",
        "legs": legs_after,
        "closed_at": closed_at.isoformat(),
        "spot_at_exit": spot_at_exit,
        "points_in_trade": points_in_trade,
        "time_in_trade_minutes": time_in_trade_minutes,
        "charges_inr": total_charges_inr,
        "exit_reason": close_reason,
        "exit_rationale": notes,
    }
    try:
        db.client.table("swayam_positions").update(pos_update_payload).eq("id", position_id).execute()
    except Exception as exc:
        logger.error("Database update to swayam_positions failed for %s: %s", position_id, exc)
        if db.url and db.key:
            raise HTTPException(
                status_code=503,
                detail=f"Database error updating position status to closed: {exc}",
            ) from exc

    # Also update local memory list
    for p in _local_paper_positions:
        if str(p.get("id")) == position_id:
            p["status"] = "closed"
            p.update(pos_update_payload)

    # Step C: Append exit report to Obsidian journal note.
    #
    # A CLOSE WITH NO NOTE YET USED TO QUEUE NOTHING AT ALL. The whole block was
    # guarded on `journal_path`, so when the entry note was still sitting in the
    # outbox — which is every trade taken on the live site, because the container
    # cannot see his vault — the exit was never written AND never queued. Two of
    # his three trades on 2026-09-09 ended in exactly that state, with a result
    # in the database and no exit in his record.
    #
    # The exit is queued regardless now. The drainer writes the entry note first
    # and appends the exit straight after, so the note is complete whenever it
    # lands.
    if not journal_path:
        queue_journal_note(
            position_id=position_id,
            payload={
                "closed_at": closed_at.isoformat(),
                "close_reason": close_reason,
                "notes": notes,
                "exit_legs": closed_legs,
                "gross_pnl_inr": gross_pnl_inr,
                "charges_inr": total_charges_inr,
                "net_pnl_inr": realized_pnl_inr,
                "max_loss_inr": max_loss,
                "holding_days": holding_days,
                "awaiting_entry_note": True,
            },
            kind="close",
            error="the entry note had not landed yet, so there was nothing to append to",
        )

    if journal_path:
        # The exit block states the result as a percentage of his capital. This
        # used to read the stored margin base and then fall back to a constant
        # in the vault; it is the live FYERS balance now, or the journal write
        # refuses rather than divide by an invented number.
        try:
            margin_base = capital_service.get_capital().risk_capital_inr
        except CapitalUnavailable as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Position closed in the database, but the live account balance is "
                    f"unavailable, so the journal exit block cannot state the result as a "
                    f"percentage of capital. {exc}"
                ),
            ) from exc

        try:
            append_exit_block(
                journal_rel_path=journal_path,
                closed_at=closed_at,
                close_reason=close_reason,
                notes=notes,
                exit_legs=closed_legs,
                gross_pnl_inr=gross_pnl_inr,
                charges_inr=total_charges_inr,
                net_pnl_inr=realized_pnl_inr,
                max_loss_inr=max_loss,
                margin_base_inr=margin_base,
                holding_days=holding_days,
            )
        except Exception as exc:
            # A NOTE IS NOT A TRADE, and this end of it was never fixed.
            #
            # Migration 019 solved exactly this on the entry side: the vault is
            # unreachable from Cloud Run, so the note write fails, and the old
            # behaviour returned an error on a trade that had already been
            # recorded, which made him press the button again. The exit side
            # still raised HTTP 500 with the position already closed in the
            # database, so his screen said the close failed when it had not.
            #
            # The note goes to the outbox instead and the close succeeds. The
            # drainer completes it from his PC, where the vault is reachable.
            logger.error("Failed to append exit block to journal %s: %s", journal_path, exc)
            journal_status = "pending"
            queued = queue_journal_note(
                position_id=position_id,
                payload={
                    "journal_rel_path": journal_path,
                    "closed_at": closed_at.isoformat(),
                    "close_reason": close_reason,
                    "notes": notes,
                    "exit_legs": closed_legs,
                    "gross_pnl_inr": gross_pnl_inr,
                    "charges_inr": total_charges_inr,
                    "net_pnl_inr": realized_pnl_inr,
                    "max_loss_inr": max_loss,
                    "margin_base_inr": margin_base,
                    "holding_days": holding_days,
                },
                kind="close",
                error=str(exc),
            )
            if not queued:
                journal_status = "failed"
            mark_journal_status(position_id, journal_status)

    # Step D: Auto-generate lesson into Lesson Ledger
    lesson_info = None
    try:
        from swayam.api.routes.lessons import generate_lesson_for_position
        pos_record_for_lesson = {**pos, **pos_update_payload, "realized_pnl_inr": realized_pnl_inr}
        lesson_record = generate_lesson_for_position(
            position_id=position_id,
            pos_record=pos_record_for_lesson,
            realized_pnl=realized_pnl_inr,
            trade_outcome=outcome,
        )
        if lesson_record:
            lesson_info = {
                "id": str(lesson_record.get("id", "")),
                "lesson_text": str(lesson_record.get("lesson_text", "")),
                "lesson_source": str(lesson_record.get("lesson_source", "ai_generated")),
            }
    except Exception as exc:
        logger.warning("Auto lesson generation failed on trade close: %s", exc)

    # Step E: Best-effort event notification dispatch (Telegram + Browser Push)
    try:
        from swayam.notifications.events import dispatch
        session_id = None
        if pos.get("notes") and "session_id=" in str(pos["notes"]):
            session_id = str(pos["notes"]).split("session_id=")[-1].split(";")[0].strip()
        dispatch("trade_closed", {
            "position_id": position_id,
            "strategy": pos.get("strategy_name", "Options Strategy"),
            "pnl_inr": realized_pnl_inr,
            "close_reason": close_reason,
            "mode": pos.get("mode", "paper"),
            "session_id": session_id or position_id[:8],
        })
    except Exception as exc:
        logger.warning("Could not dispatch trade_closed event: %s", exc)

    return ClosePositionResponse(
        position_id=position_id,
        status="closed",
        gross_pnl_inr=round(gross_pnl_inr, 2),
        realized_pnl_inr=round(realized_pnl_inr, 2),
        total_charges_inr=round(total_charges_inr, 2),
        exit_legs=closed_legs,
        journal_path=journal_path,
        lesson=lesson_info,
    )


class RenamePositionRequest(BaseModel):
    """His own name for a trade, or the word back to the structure's."""

    name: Optional[str] = Field(default=None, max_length=120)


@router.patch("/api/positions/{position_id}/name")
def rename_position(position_id: str, req: RenamePositionRequest) -> dict[str, Any]:
    """Names a trade himself, or hands the naming back to the structure.

    His words, 2026-09-10: "Short Strangle was not the name chosen by me. It
    was the system error that gave it the name... I had no role to play in
    naming any order I made today."

    So a name he types is recorded as his and nothing overwrites it, however
    the legs change afterwards. Sending an empty name puts him back on the
    derived one, which recomputes from the open legs from that moment on.

    This touches the name and nothing else. It cannot move a price, a fill or
    a charge, and it works on a closed trade as well as an open one, because
    a trade in the record is allowed a better name after the fact.
    """
    try:
        res = db.client.table("swayam_positions").select("*").eq("id", position_id).execute()
        pos = res.data[0] if res.data else None
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Could not read position {position_id}: {exc}") from exc
    if pos is None:
        raise HTTPException(status_code=404, detail=f"Position '{position_id}' not found.")

    typed = (req.name or "").strip()
    if typed:
        update = {"strategy_name": typed, "name_source": "his"}
        message = f"Named \"{typed}\". The terminal will not rename it again."
    else:
        derived = name_from_legs(pos.get("legs") or [])
        update = {"strategy_name": derived, "name_source": "structure"}
        message = (
            f"Back to the structure's own name, \"{derived}\". "
            "It follows the open legs from here on."
        )

    try:
        db.client.table("swayam_positions").update(update).eq("id", position_id).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"The name could not be saved, so nothing changed. {exc}",
        ) from exc

    for p in _local_paper_positions:
        if str(p.get("id")) == position_id:
            p.update(update)

    return {
        "position_id": position_id,
        "strategy_name": update["strategy_name"],
        "name_source": update["name_source"],
        "message": message,
    }


@router.get("/api/phase")
def get_phase() -> dict[str, Any]:
    """Has paper trading begun, and how confidently that is known.

    One timestamp, set by `scripts/start_paper_trading.py`, which HE runs on
    the day he decides. Until then every trade the terminal records is a
    terminal test: a real fill with real charges that he took to see how the
    terminal behaves, not a trade he planned.

    The reply carries `source`, so a screen can say whether this is the table's
    answer or the safe reading of an unreadable table. It never guesses a date.
    """
    return read_phase().to_dict()


class LegTargetItem(BaseModel):
    """One leg's pair of prices. Either may be blank, and blank clears it."""

    sequence: int
    target_price: Optional[float] = None
    stop_price: Optional[float] = None


class SetTargetsRequest(BaseModel):
    """What he typed into the Targets modal. Every box may be blank.

    His words, 2026-09-10: "My preference is to add a target for each leg.
    Target always means both loss and profit... In case I cannot add profit and
    loss for each leg, I have to add it for the whole trade."

    A blank box CLEARS that target. It never means zero and it never means
    leave it as it was, because a modal he can see is the whole truth of what
    is set: if he emptied a box and pressed Save, he meant to empty it.
    """

    legs: list[LegTargetItem] = Field(default_factory=list)
    target_profit_inr: Optional[float] = None
    target_loss_inr: Optional[float] = None


@router.put("/api/positions/{position_id}/targets")
def set_position_targets(position_id: str, req: SetTargetsRequest) -> dict[str, Any]:
    """Saves what he wants this trade to tell him. It changes nothing else.

    THIS ROUTE CANNOT MOVE MONEY. It writes two numbers on the row and two
    numbers on each leg of the `legs` JSON, and it touches no order, no fill,
    no charge and no result. A reached target lights Home up and waits for him.

    A CLOSED TRADE IS REFUSED, because a target on a trade that is already in
    the record would be a signal that can never fire, sitting where he would
    read it as live.

    A blank box clears. A loss figure is stored as a size, so a minus sign he
    types is taken as emphasis rather than as a direction, and a zero is
    treated as blank: zero is not a level, it is an empty box with a keystroke
    in it.
    """
    try:
        res = db.client.table("swayam_positions").select("*").eq("id", position_id).execute()
        pos = res.data[0] if res.data else None
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"Could not read position {position_id}: {exc}"
        ) from exc
    if pos is None:
        raise HTTPException(status_code=404, detail=f"Position '{position_id}' not found.")

    if str(pos.get("status") or "").lower() == "closed":
        raise HTTPException(
            status_code=409,
            detail=(
                "This trade is closed, so a target on it could never fire. "
                "Targets belong on a trade you still hold."
            ),
        )

    def level(value: Optional[float]) -> Optional[float]:
        """A price or a rupee figure he typed, or None for an empty box."""
        if value is None:
            return None
        try:
            out = float(value)
        except (TypeError, ValueError):
            return None
        if out != out or out in (float("inf"), float("-inf")):
            return None
        # Zero is an empty box with a keystroke in it, not a level.
        return None if out == 0 else out

    wanted = {int(item.sequence): item for item in req.legs}
    legs = [dict(leg) for leg in (pos.get("legs") or [])]
    legs_touched = 0
    unknown = sorted(
        seq
        for seq in wanted
        if seq not in {int(leg.get("sequence")) for leg in legs if leg.get("sequence") is not None}
    )
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=(
                f"This trade has no leg {', '.join(str(u) for u in unknown)}, "
                "so nothing was saved."
            ),
        )

    for leg in legs:
        seq = leg.get("sequence")
        if seq is None or int(seq) not in wanted:
            continue
        item = wanted[int(seq)]
        take, cut = level(item.target_price), level(item.stop_price)
        if take is not None and take < 0:
            raise HTTPException(
                status_code=400,
                detail=f"A take-profit price cannot be negative (leg {seq}). Nothing was saved.",
            )
        if cut is not None and cut < 0:
            raise HTTPException(
                status_code=400,
                detail=f"A cut-loss price cannot be negative (leg {seq}). Nothing was saved.",
            )
        wrong = wrong_side_of_entry(leg, target_price=take, stop_price=cut)
        if wrong is not None:
            raise HTTPException(status_code=400, detail=f"{wrong} Nothing was saved.")
        leg["target_price"] = take
        leg["stop_price"] = cut
        legs_touched += 1

    profit = level(req.target_profit_inr)
    loss = level(req.target_loss_inr)
    # A loss is a size. A minus sign he typed is emphasis, not a direction.
    if loss is not None:
        loss = abs(loss)
    if profit is not None and profit < 0:
        raise HTTPException(
            status_code=400,
            detail="A profit target below zero is a loss wearing the wrong label. Nothing was saved.",
        )

    anything_set = (
        profit is not None
        or loss is not None
        or any(
            leg.get("target_price") is not None or leg.get("stop_price") is not None
            for leg in legs
        )
    )

    update = {
        "legs": legs,
        "target_profit_inr": profit,
        "target_loss_inr": loss,
        # Cleared everything? Then he has no targets set, and the stamp goes
        # with them rather than claiming he set something at that moment.
        "targets_set_at": datetime.now(timezone.utc).isoformat() if anything_set else None,
    }

    try:
        db.client.table("swayam_positions").update(update).eq("id", position_id).execute()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "The targets could not be saved, so nothing changed. "
                "Your trade and your legs are exactly as they were. "
                f"{exc}"
            ),
        ) from exc

    for p in _local_paper_positions:
        if str(p.get("id")) == position_id:
            p.update(update)

    leg_count = sum(
        1
        for leg in legs
        if leg.get("target_price") is not None or leg.get("stop_price") is not None
    )
    if not anything_set:
        message = "Targets cleared. This trade will not signal you until you set one."
    else:
        bits = []
        if leg_count:
            bits.append(f"{leg_count} leg{'' if leg_count == 1 else 's'}")
        if profit is not None or loss is not None:
            bits.append("the whole trade")
        message = "Targets saved on " + " and ".join(bits) + "."
        if loss is None:
            message += " With the trade loss blank, rule 1 stands in, read live."

    return {
        "position_id": position_id,
        "legs_updated": legs_touched,
        "target_profit_inr": profit,
        "target_loss_inr": loss,
        "targets_set_at": update["targets_set_at"],
        "message": message,
    }


@router.get("/api/positions/naked-shorts")
def detect_naked_shorts(
    at_time: str = Query(default="15:20", description="Evaluation time in IST (e.g. 15:20)"),
) -> dict[str, Any]:
    """Evaluates open positions for unhedged/naked short legs.

    Enforces Risk Management Rules § 10a (No overnight naked shorts).
    Fires block modal on frontend at 15:20 IST.
    """
    open_positions: list[dict[str, Any]] = []

    # 1. Fetch from Supabase
    try:
        res = db.client.table("swayam_positions").select("*").eq("status", "open").execute()
        if res.data:
            open_positions.extend(res.data)
    except Exception as exc:
        logger.error("Naked-shorts safety check failed: Supabase unreachable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "Naked-shorts safety check unavailable: cannot reach Supabase to enumerate open positions. "
                "This is a safety-critical endpoint — do not assume 'no naked shorts' when the database is unreachable. "
                "Retry when Supabase is reachable, or manually inspect open positions from your broker terminal. "
                f"Underlying error: {exc}"
            ),
        ) from exc

    # 2. Append local in-memory paper positions
    seen_ids = {str(p.get("id")) for p in open_positions}
    for p in _local_paper_positions:
        p_id = str(p.get("id"))
        if p.get("status") == "open" and p_id not in seen_ids:
            open_positions.append(p)
            seen_ids.add(p_id)

    violations: list[dict[str, Any]] = []

    for pos in open_positions:
        legs = pos.get("legs", [])
        if not isinstance(legs, list) or not legs:
            continue

        sold_calls: list[dict[str, Any]] = []
        bought_calls: list[dict[str, Any]] = []
        sold_puts: list[dict[str, Any]] = []
        bought_puts: list[dict[str, Any]] = []

        for leg in legs:
            d = str(leg.get("direction", "")).lower()
            t = str(leg.get("option_type", "")).upper()
            qty = int(leg.get("quantity_lots", 1) or 1)

            if d == "sell":
                if t in ("CE", "CALL"):
                    sold_calls.append(leg)
                elif t in ("PE", "PUT"):
                    sold_puts.append(leg)
            elif d == "buy":
                if t in ("CE", "CALL"):
                    bought_calls.append(leg)
                elif t in ("PE", "PUT"):
                    bought_puts.append(leg)

        total_sold_call_qty = sum(int(l.get("quantity_lots", 1) or 1) for l in sold_calls)
        total_bought_call_qty = sum(int(l.get("quantity_lots", 1) or 1) for l in bought_calls)
        total_sold_put_qty = sum(int(l.get("quantity_lots", 1) or 1) for l in sold_puts)
        total_bought_put_qty = sum(int(l.get("quantity_lots", 1) or 1) for l in bought_puts)

        naked_short_legs: list[dict[str, Any]] = []
        suggested_hedges: list[dict[str, Any]] = []

        # Unhedged Calls check
        if total_sold_call_qty > total_bought_call_qty:
            diff = total_sold_call_qty - total_bought_call_qty
            naked_short_legs.extend(sold_calls)
            max_call_strike = max((float(l.get("strike", 25000)) for l in sold_calls), default=25000)
            suggested_hedges.append({
                "action": "BUY",
                "option_type": "CE",
                "strike": max_call_strike + 150.0,
                "quantity_lots": diff,
                "expiry_date": sold_calls[0].get("expiry_date", str(date.today())),
                "rationale": f"Hedge short call risk with OTM call wing at {max_call_strike + 150.0}",
            })

        # Unhedged Puts check
        if total_sold_put_qty > total_bought_put_qty:
            diff = total_sold_put_qty - total_bought_put_qty
            naked_short_legs.extend(sold_puts)
            min_put_strike = min((float(l.get("strike", 24500)) for l in sold_puts), default=24500)
            suggested_hedges.append({
                "action": "BUY",
                "option_type": "PE",
                "strike": max(50.0, min_put_strike - 150.0),
                "quantity_lots": diff,
                "expiry_date": sold_puts[0].get("expiry_date", str(date.today())),
                "rationale": f"Hedge short put downside risk with OTM put wing at {min_put_strike - 150.0}",
            })

        if naked_short_legs:
            violations.append({
                "position_id": str(pos.get("id")),
                "strategy_name": pos.get("strategy_name", "Open Spread"),
                "underlying": pos.get("underlying", "NIFTY"),
                "naked_legs": naked_short_legs,
                "suggested_hedges": suggested_hedges,
                "rule_citation": "Risk Management Rules § 10a — no overnight naked. Overnight hedge cap: 2% of margin base.",
            })

    return {
        "at_time": at_time,
        "has_naked_shorts": len(violations) > 0,
        "violations": violations,
    }
