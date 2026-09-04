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
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from swayam.api.journal_writer import append_exit_block
from swayam.api.models_api import PositionResponse
from swayam.config import settings
from swayam.db import db
from swayam.fyers_client import FyersClientError, fyers_client
from swayam.options_math.greeks import compute_position_greeks
from swayam.options_math.models import Direction, Leg, OptionType, Spread

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory store for paper positions in local mode
_local_paper_positions: list[dict[str, Any]] = []

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
    position_id: str
    status: str
    realized_pnl_inr: float
    total_charges_inr: float
    journal_path: Optional[str] = None


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
        raw_chain = fyers_client.get_option_chain(
            underlying=underlying,
            strike_count=40,
            timestamp=expiry,
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

    for item in options_chain:
        strike = float(item.get("strike_price") or item.get("strike") or 0.0)

        # Dual CE/PE format (FYERS standard optionsChain item)
        if "call_ltp" in item or "call_symbol" in item:
            lookup[(strike, "CE")] = {
                "ltp": float(item.get("call_ltp", 0.0) or 0.0),
                "iv": float(item.get("call_iv", 0.15) or 0.15),
            }
        if "put_ltp" in item or "put_symbol" in item:
            lookup[(strike, "PE")] = {
                "ltp": float(item.get("put_ltp", 0.0) or 0.0),
                "iv": float(item.get("put_iv", 0.15) or 0.15),
            }

        # Nested CE/PE format (models_api StrikeRow item)
        if "ce" in item and isinstance(item["ce"], dict):
            lookup[(strike, "CE")] = {
                "ltp": float(item["ce"].get("ltp", 0.0) or 0.0),
                "iv": float(item["ce"].get("iv", 0.15) or 0.15),
            }
        if "pe" in item and isinstance(item["pe"], dict):
            lookup[(strike, "PE")] = {
                "ltp": float(item["pe"].get("ltp", 0.0) or 0.0),
                "iv": float(item["pe"].get("iv", 0.15) or 0.15),
            }

        # Single contract item
        if "option_type" in item and "ltp" in item:
            lookup[(strike, str(item["option_type"]).upper())] = {
                "ltp": float(item.get("ltp", 0.0) or 0.0),
                "iv": float(item.get("iv", 0.15) or 0.15),
            }

    return spot, lookup


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

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

    # Merge with local session paper trades if not already present
    existing_ids = {p.get("id") for p in positions_data}
    for local_pos in _local_paper_positions:
        if local_pos.get("id") not in existing_ids and local_pos.get("status") == status:
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

    # Merge local positions
    existing_ids = {p.get("id") for p in positions_data}
    for local_pos in _local_paper_positions:
        if local_pos.get("id") not in existing_ids and local_pos.get("status") == "open":
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
        enriched_legs: list[dict[str, Any]] = []
        spread_legs: list[Leg] = []
        iv_map: dict[Leg, float] = {}

        for leg in legs:
            strike = float(leg.get("strike", 0.0))
            opt_type = str(leg.get("option_type", "CE")).upper()
            qty_lots = int(leg.get("quantity_lots", 1) or 1)
            lot_size = int(leg.get("lot_size", 75) or 75)
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
            leg_copy["current_iv"] = quote.get("iv", 0.15)
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
                leg_obj = Leg(
                    strike=strike,
                    option_type=OptionType.CALL if opt_type == "CE" else OptionType.PUT,
                    direction=Direction.BUY if is_buy else Direction.SELL,
                    quantity_lots=qty_lots,
                    lot_size=lot_size,
                    entry_premium=float(leg.get("entry_premium", 0.0) or 0.0),
                    expiry_date=exp_date,
                    iv=float(quote.get("iv", 0.15) or 0.15),
                )
                spread_legs.append(leg_obj)
                iv_map[leg_obj] = float(quote.get("iv", 0.15) or 0.15)
            except Exception:
                pass

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
                logger.debug("Failed to compute live Greeks: %s", e)

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
                    days_held=days_held,
                    days_remaining_to_expiry=days_remaining,
                    journal_path=journal_path,
                    error=None,
                )
            )

    return results


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
    journal_path = pos.get("journal_path")
    underlying = pos.get("underlying", "NIFTY")
    expiry_val = pos.get("expiry_date") or (legs[0].get("expiry_date") if legs else None)

    # 2. Resolve exit premiums per leg
    # If exit_legs provided, use them; otherwise fetch from FYERS option chain
    chain_lookup: dict[tuple[float, str], dict[str, Any]] = {}
    if not req.exit_legs:
        raw_chain = _get_cached_option_chain(underlying, expiry=expiry_val)
        _, chain_lookup = _build_chain_lookup(raw_chain)

    gross_exit_value = 0.0
    closed_legs: list[dict[str, Any]] = []

    for leg in legs:
        strike = float(leg.get("strike", 0.0))
        opt_type = str(leg.get("option_type", "CE")).upper()
        qty_lots = int(leg.get("quantity_lots", 1) or 1)
        lot_size = int(leg.get("lot_size", 75) or 75)
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

        closed_legs.append({
            "strike": strike,
            "option_type": opt_type,
            "direction": direction,
            "quantity_lots": qty_lots,
            "lot_size": lot_size,
            "entry_premium": entry_prem,
            "exit_premium": exit_prem,
        })

    # 3. Compute Realized P&L and Estimated Charges
    gross_pnl_inr = gross_exit_value
    total_charges_inr = len(closed_legs) * settings.estimated_charge_per_leg_inr
    realized_pnl_inr = gross_pnl_inr - total_charges_inr


    closed_at = datetime.now(timezone.utc)
    opened_at_str = str(pos.get("opened_at", closed_at.isoformat()))
    try:
        opened_at_dt = datetime.fromisoformat(opened_at_str.replace("Z", "+00:00"))
        holding_days = max(0, (closed_at.date() - opened_at_dt.date()).days)
    except Exception:
        holding_days = 0

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

    try:
        db.client.table("swayam_trade_history").insert(trade_history_record).execute()
    except Exception as exc:
        logger.error("Database insert to swayam_trade_history failed for %s: %s", position_id, exc)
        if db.url and db.key:
            raise HTTPException(
                status_code=503,
                detail=f"Database error writing trade history: {exc}",
            ) from exc

    # Step B: Update swayam_positions status to 'closed'
    try:
        db.client.table("swayam_positions").update({"status": "closed"}).eq("id", position_id).execute()
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

    # Step C: Append exit report to Obsidian journal note
    if journal_path:
        try:
            margin_base = db.get_margin_base_inr()
        except Exception:
            try:
                from swayam.vault_reader import vault_reader
                margin_base = vault_reader.load_rules().margin_base_default_inr
            except Exception:
                raise HTTPException(
                    status_code=503,
                    detail="Database and Method Rules unreachable to determine margin base for journal exit block.",
                )

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
            logger.error("Failed to append exit block to journal %s: %s", journal_path, exc)
            raise HTTPException(
                status_code=500,
                detail=f"Trade closed in DB, but writing to journal note failed: {exc}",
            ) from exc

    return ClosePositionResponse(
        position_id=position_id,
        status="closed",
        realized_pnl_inr=round(realized_pnl_inr, 2),
        total_charges_inr=round(total_charges_inr, 2),
        journal_path=journal_path,
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
