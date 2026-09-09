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
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from swayam.api.journal_writer import append_exit_block
from swayam.services.execution_safety import mark_journal_status, queue_journal_note
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
    position_id: str
    strategy_name: str
    underlying: str
    opened_at: str
    expiry_date: Optional[str] = None
    legs: list[dict[str, Any]]
    entry_debit_credit_inr: float
    max_loss_inr: float
    max_profit_inr: float
    current_spot: Optional[float] = None
    current_position_value_inr: Optional[float] = None
    unrealized_pnl_inr: Optional[float] = None
    unrealized_pnl_pct_of_risk: Optional[float] = None
    current_greeks: Optional[LivePositionGreeks] = None
    greeks_unavailable_reason: Optional[str] = None
    days_held: int
    days_remaining_to_expiry: int
    journal_path: Optional[str] = None
    error: Optional[str] = None


class CloseLegItem(BaseModel):
    strike: float
    option_type: str
    exit_premium: float


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
    """Fetches option chain from FYERS with a 5-second cache to avoid hitting rate limits."""
    cache_key = f"{underlying}_{expiry or 'all'}"
    now = time.time()

    if cache_key in _chain_cache:
        entry = _chain_cache[cache_key]
        if (now - entry["timestamp"]) < 5.0:
            return entry["data"]

    try:
        # THIS CALL HAD NEVER WORKED ONCE. It passed the position's underlying,
        # the word "NIFTY", where FYERS wants a symbol, and an ISO date where it
        # wants an expiry epoch. FYERS answered "Please provide a valid symbol",
        # so /api/positions/live raised 503 every single time and his open
        # position showed "profit and loss unavailable". Proven against live
        # FYERS on 2026-09-09.
        from swayam.api.routes.market import resolve_expiry_epoch

        symbol = _FYERS_INDEX_SYMBOLS.get(str(underlying).upper(), str(underlying))

        # Resolving the epoch costs one small extra call, so it is best effort:
        # if it cannot be resolved we ask for the chain without one rather than
        # refusing outright. The symbol is the part that was actually fatal.
        epoch: Optional[str] = None
        if expiry:
            cache_key_epoch = f"{symbol}|{expiry}"
            cached = _expiry_epoch_cache.get(cache_key_epoch)
            if cached and (now - cached[1]) < 600.0:
                epoch = cached[0]
            else:
                try:
                    # One small call, cached for ten minutes, because the desk
                    # polls positions and the FYERS request budget is finite.
                    base = fyers_client.get_option_chain(underlying=symbol, strike_count=2)
                    epoch = resolve_expiry_epoch(base, str(expiry))
                    if epoch:
                        _expiry_epoch_cache[cache_key_epoch] = (epoch, now)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Could not resolve the expiry epoch for %s: %s", expiry, exc)
            if not epoch:
                logger.warning(
                    "FYERS did not list an expiry on %s; reading the chain without one.",
                    expiry,
                )

        raw_chain = fyers_client.get_option_chain(
            underlying=symbol,
            strike_count=40,
            timestamp=epoch,
        )
        _chain_cache[cache_key] = {"data": raw_chain, "timestamp": now}
        return raw_chain
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
        if "call_ltp" in item or "call_symbol" in item:
            lookup[(strike, "CE")] = {
                "ltp": _num(item.get("call_ltp")),
                "iv": _num(item.get("call_iv")),
            }
        if "put_ltp" in item or "put_symbol" in item:
            lookup[(strike, "PE")] = {
                "ltp": _num(item.get("put_ltp")),
                "iv": _num(item.get("put_iv")),
            }

        # Nested CE/PE format (models_api StrikeRow item)
        if "ce" in item and isinstance(item["ce"], dict):
            lookup[(strike, "CE")] = {
                "ltp": _num(item["ce"].get("ltp")),
                "iv": _num(item["ce"].get("iv")),
            }
        if "pe" in item and isinstance(item["pe"], dict):
            lookup[(strike, "PE")] = {
                "ltp": _num(item["pe"].get("ltp")),
                "iv": _num(item["pe"].get("iv")),
            }

        # Single contract item
        if "option_type" in item and "ltp" in item:
            lookup[(strike, str(item["option_type"]).upper())] = {
                "ltp": _num(item.get("ltp")),
                "iv": _num(item.get("iv")),
            }

    return spot, lookup


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

    results: list[PositionResponse] = []
    for p in positions_data:
        results.append(
            PositionResponse(
                id=str(p.get("id")),
                strategy_name=p.get("strategy_name", "Unknown Strategy"),
                underlying=p.get("underlying", "NIFTY"),
                legs=p.get("legs", []),
                net_debit_credit_inr=float(p.get("net_debit_credit_inr", 0.0)),
                max_loss_inr=float(p.get("max_loss_inr", 0.0)),
                max_profit_inr=float(p.get("max_profit_inr", 0.0)),
                breakeven_points=p.get("breakeven_points", []),
                status=p.get("status", "open"),
                mode=p.get("mode", "paper"),
                opened_at=str(p.get("opened_at")),
                unrealized_pnl_inr=float(p.get("unrealized_pnl_inr", 0.0)),
                journal_path=p.get("journal_path"),
            )
        )

    return results


@router.get("/api/positions/live", response_model=list[LivePositionResponse])
def get_positions_live() -> list[LivePositionResponse]:
    """Returns all open paper positions with live P&L and Greeks computed against FYERS.

    Polled every 5 seconds by the frontend Active Trades panel.
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

    # Map positions against live chain
    results: list[LivePositionResponse] = []

    for pos in positions_data:
        position_id = str(pos.get("id"))
        strategy_name = pos.get("strategy_name", "Options Strategy")
        underlying = pos.get("underlying", "NIFTY")
        opened_at_str = str(pos.get("opened_at", datetime.now(timezone.utc).isoformat()))
        legs = pos.get("legs", [])
        entry_debit_credit = float(pos.get("net_debit_credit_inr", 0.0))
        max_loss = float(pos.get("max_loss_inr", 0.0))
        max_profit = float(pos.get("max_profit_inr", 0.0))
        journal_path = pos.get("journal_path")

        # Determine expiry date
        expiry_val = pos.get("expiry_date")
        if not expiry_val and legs:
            expiry_val = legs[0].get("expiry_date")

        # Fetch option chain from FYERS (cached 5s)
        try:
            raw_chain = _get_cached_option_chain(underlying, expiry=expiry_val)
            spot, chain_lookup = _build_chain_lookup(raw_chain)
            if spot <= 0.0:
                spot = fyers_client.get_nifty_spot()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"Cannot compute live P&L: FYERS chain unreachable ({e}).",
            ) from e

        # Calculate position valuation
        unrealized_pnl_total = 0.0
        current_position_value = 0.0
        missing_strike = False
        greeks_unavailable_reason: Optional[str] = None
        enriched_legs: list[dict[str, Any]] = []
        spread_legs: list[Leg] = []
        iv_map: dict[Leg, float] = {}

        for leg in legs:
            strike = float(leg.get("strike", 0.0))
            opt_type = str(leg.get("option_type", "CE")).upper()
            qty_lots = int(leg.get("quantity_lots", 1) or 1)
            # The contract size recorded when the position was opened. A stored
            # position must be valued at the size it was actually booked with,
            # not at today's contract master. Missing is an error, not a 75:
            # the 67 legacy rows were booked at 75, which was never the real
            # NIFTY lot, and they are quarantined rather than re-valued.
            stored_lot = leg.get("lot_size")
            if not stored_lot:
                missing_strike = True
                leg_copy = dict(leg)
                leg_copy["error"] = "lot_size_missing_on_stored_leg"
                enriched_legs.append(leg_copy)
                continue
            lot_size = int(stored_lot)
            contracts = qty_lots * lot_size
            direction = str(leg.get("direction", "buy")).lower()
            is_buy = direction in ("buy", "long")
            entry_prem = float(leg.get("entry_premium", 0.0) or 0.0)

            quote = chain_lookup.get((strike, opt_type))
            if quote is None or quote.get("ltp") is None:
                missing_strike = True
                leg_copy = dict(leg)
                leg_copy["error"] = "strike_not_in_current_chain"
                enriched_legs.append(leg_copy)
                continue

            current_ltp = float(quote["ltp"])
            leg_val = (current_ltp * contracts) if is_buy else (-current_ltp * contracts)
            leg_pnl = ((current_ltp - entry_prem) * contracts) if is_buy else ((entry_prem - current_ltp) * contracts)

            current_position_value += leg_val
            unrealized_pnl_total += leg_pnl

            leg_copy = dict(leg)
            leg_copy["current_ltp"] = current_ltp
            leg_copy["current_iv"] = quote.get("iv")  # may be None: show "-", never 0.15
            leg_copy["current_value_inr"] = leg_val
            leg_copy["unrealized_pnl_inr"] = leg_pnl
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
                    entry_premium=float(leg.get("entry_premium", 0.0) or 0.0),
                    expiry_date=exp_date,
                )
                spread_legs.append(leg_obj)
                iv_map[leg_obj] = float(leg_iv)
            except Exception as exc:
                # Never silent again. A leg that cannot be modelled makes the
                # greeks unavailable and says so.
                greeks_unavailable_reason = f"could not model a leg: {exc}"
                logger.warning("Position leg could not be modelled for greeks: %s", exc)

        # Compute Greeks
        live_greeks: Optional[LivePositionGreeks] = None
        if not missing_strike and spread_legs and spot > 0:
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

        # Days held & days to expiry
        try:
            opened_at_dt = datetime.fromisoformat(opened_at_str.replace("Z", "+00:00"))
            days_held = max(0, (datetime.now(timezone.utc).date() - opened_at_dt.date()).days)
        except Exception:
            days_held = 0

        try:
            if expiry_val:
                exp_dt = datetime.fromisoformat(str(expiry_val)).date()
                days_remaining = max(0, (exp_dt - date.today()).days)
            else:
                days_remaining = 0
        except Exception:
            days_remaining = 0

        if missing_strike:
            results.append(
                LivePositionResponse(
                    position_id=position_id,
                    strategy_name=strategy_name,
                    underlying=underlying,
                    opened_at=opened_at_str,
                    expiry_date=str(expiry_val) if expiry_val else None,
                    legs=enriched_legs,
                    entry_debit_credit_inr=entry_debit_credit,
                    max_loss_inr=max_loss,
                    max_profit_inr=max_profit,
                    current_spot=spot,
                    current_position_value_inr=None,
                    unrealized_pnl_inr=None,
                    unrealized_pnl_pct_of_risk=None,
                    current_greeks=None,
                    days_held=days_held,
                    days_remaining_to_expiry=days_remaining,
                    journal_path=journal_path,
                    error="strike_not_in_current_chain",
                )
            )
        else:
            unrealized_pnl = unrealized_pnl_total
            unrealized_pct = (unrealized_pnl / max_loss) if max_loss > 0 else 0.0


            results.append(
                LivePositionResponse(
                    position_id=position_id,
                    strategy_name=strategy_name,
                    underlying=underlying,
                    opened_at=opened_at_str,
                    expiry_date=str(expiry_val) if expiry_val else None,
                    legs=enriched_legs,
                    entry_debit_credit_inr=entry_debit_credit,
                    max_loss_inr=max_loss,
                    max_profit_inr=max_profit,
                    current_spot=spot,
                    current_position_value_inr=round(current_position_value, 2),
                    unrealized_pnl_inr=round(unrealized_pnl, 2),
                    unrealized_pnl_pct_of_risk=round(unrealized_pct, 4),
                    current_greeks=live_greeks,
                    greeks_unavailable_reason=(
                        None if live_greeks else (greeks_unavailable_reason or "greeks not computed")
                    ),
                    days_held=days_held,
                    days_remaining_to_expiry=days_remaining,
                    journal_path=journal_path,
                    error=None,
                )
            )

    return results


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


@router.post("/api/positions/{position_id}/close", response_model=ClosePositionResponse)
def close_position(position_id: str, req: ClosePositionRequest) -> ClosePositionResponse:
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
    max_loss = float(pos.get("max_loss_inr", 0.0))
    journal_path = _resolve_journal_path(pos, position_id)
    underlying = pos.get("underlying", "NIFTY")
    expiry_val = pos.get("expiry_date") or (legs[0].get("expiry_date") if legs else None)

    # 2. Resolve exit premiums per leg
    # If exit_legs provided, use them; otherwise fetch from FYERS option chain
    chain_lookup: dict[tuple[float, str], dict[str, Any]] = {}
    spot_at_exit: Optional[float] = None
    if not req.exit_legs:
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

    gross_exit_value = 0.0
    total_entry_charges = 0.0
    total_exit_charges = 0.0
    closed_legs: list[dict[str, Any]] = []

    for leg in legs:
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

        if req.exit_legs:
            for el in req.exit_legs:
                if abs(float(el.strike) - strike) < 0.01 and el.option_type.upper() == opt_type:
                    exit_prem = float(el.exit_premium)
                    break
        else:
            quote = chain_lookup.get((strike, opt_type))
            if quote and quote.get("ltp") is not None:
                exit_prem = float(quote["ltp"])

        if exit_prem is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Cannot close position: Missing exit premium for {strike} {opt_type}. "
                    "Supply exit_legs explicitly or check FYERS option chain."
                ),
            )

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

        closed_legs.append({
            "strike": strike,
            "option_type": opt_type,
            "direction": direction,
            "quantity_lots": qty_lots,
            "lot_size": lot_size,
            "entry_premium": entry_prem,
            "exit_premium": exit_prem,
            # Per leg, the three figures he asked for.
            "gross_pnl_inr": round(leg_pnl, 2),
            "entry_charges_inr": round(entry_cost_inr, 2),
            "exit_charges_inr": round(exit_cost_inr, 2),
            "charges_inr": leg_charges,
            "net_pnl_inr": round(leg_pnl - leg_charges, 2),
            "entry_charges_source": entry_charges_source,
            "charges_schedule_version": exit_cost.schedule_version,
        })

    # 3. Compute Realized P&L and Estimated Charges
    # The trade's three figures, each the sum of its legs': cumulative gross,
    # cumulative charges for the whole round trip, and the net after them.
    gross_pnl_inr = round(gross_exit_value, 2)
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
        "close_reason": req.close_reason,
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
        "closed_at": closed_at.isoformat(),
        "spot_at_exit": spot_at_exit,
        "points_in_trade": points_in_trade,
        "time_in_trade_minutes": time_in_trade_minutes,
        "charges_inr": total_charges_inr,
        "exit_reason": req.close_reason,
        "exit_rationale": req.notes,
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
                "close_reason": req.close_reason,
                "notes": req.notes,
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
                close_reason=req.close_reason,
                notes=req.notes,
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
                    "close_reason": req.close_reason,
                    "notes": req.notes,
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
            "close_reason": req.close_reason,
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
