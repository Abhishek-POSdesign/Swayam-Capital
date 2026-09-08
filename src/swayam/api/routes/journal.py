"""
Trade Journal & Performance Analytics Endpoints for Swayam Capital (BUILD-11).

Provides:
- GET /api/journal/trades — List filtered, sorted, paginated trades with 7 KPI strip
- GET /api/journal/trade/{position_id} — Single trade deep inspection
- GET /api/journal/analytics — Aggregated edge analytics (cumulative curve, exit reason, trend)
"""

from datetime import datetime
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from swayam.api.models_api import (
    ArchiveTestTradesResponse,
    JournalKPIs,
    JournalTradeItem,
    JournalTradesResponse,
)
from swayam.db import db
from swayam.services.capital import CapitalUnavailable, get_capital

logger = logging.getLogger(__name__)

# The one mark that says a row is not one of his trades. `provenance` is the
# column built for this in migration 017. The old second mark was
# `status = 'archived'`, applied by a hardcoded date cutoff of 2026-09-06, and
# the two could disagree. His own question, 2026-09-08: "I'm not aware of how
# you are making a row. Know that it is not a real trade, and I am never aware
# of it." There is now one mark, it is filtered here, and the count of what it
# excluded is returned so a screen can say so.
LIVE_PROVENANCE = "live"


def _capital_base() -> tuple[Optional[float], str]:
    """His live balance, or the reason it cannot be read. Never a constant.

    This used to be a hardcoded five-lakh figure in two places, neither his
    balance nor a figure anyone chose. Execution and positions already read the
    real account; the record now does too, and says `unavailable` when it
    cannot rather than dividing by an invented number.
    """
    try:
        snap = get_capital()
        return snap.risk_capital_inr, snap.source
    except CapitalUnavailable as exc:
        return None, f"live capital unavailable: {exc}"
    except Exception as exc:  # noqa: BLE001 - the reason matters more than the type
        logger.warning("Could not read live capital for the journal: %s", exc)
        return None, f"live capital unavailable: {exc}"


def _pct(numerator: float, denominator: Optional[float]) -> Optional[float]:
    """A percentage, or nothing at all when there is no honest denominator."""
    if denominator is None or denominator <= 0:
        return None
    return round(numerator / denominator * 100, 2)

router = APIRouter()


def _format_time_in_trade(minutes: Optional[int]) -> str:
    """Formats wall-clock minutes into human-readable duration (e.g., 2d 3h or 2h 15m)."""
    if minutes is None or minutes < 0:
        return "—"
    if minutes >= 1440:
        days = minutes // 1440
        rem_hours = (minutes % 1440) // 60
        return f"{days}d {rem_hours}h"
    elif minutes >= 60:
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours}h {mins}m"
    else:
        return f"{minutes}m"


def _format_legs_summary(legs: list[dict[str, Any]]) -> str:
    """Summarises legs array into compact readable format (e.g. BUY 25000 PE / SELL 24800 PE (1 lot))."""
    if not legs:
        return "No legs"
    parts = []
    lots = 1
    for leg in legs:
        direction = str(leg.get("direction", "")).upper()
        strike = leg.get("strike", "")
        opt_type = leg.get("option_type", "")
        lots = leg.get("quantity_lots", lots)
        parts.append(f"{direction} {strike} {opt_type}")
    return f"{' / '.join(parts)} ({lots} lot{'s' if lots > 1 else ''})"


@router.get("/api/journal/trades", response_model=JournalTradesResponse)
def get_journal_trades(
    status: str = Query(default="all", description="all | open | closed"),
    mode: str = Query(default="all", description="all | paper | real"),
    outcome: str = Query(default="all", description="all | win | loss | breakeven"),
    strategy: Optional[str] = Query(default=None, description="Strategy preset filter"),
    exit_reason: Optional[str] = Query(default=None, description="Exit reason filter"),
    discipline: str = Query(default="all", description="all | followed | broken"),
    directional_view: Optional[str] = Query(default=None, description="Bullish | Bearish | Neutral | Range-bound"),
    from_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="ISO date YYYY-MM-DD"),
    sort_by: str = Query(default="date_desc", description="date_desc | date_asc | pnl_desc | pnl_asc"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JournalTradesResponse:
    """Returns paginated trades matching filters along with dynamically computed 7 KPIs."""
    # 1. Query Supabase positions with fail-loud 503 discipline
    try:
        client = db.client
        query = client.table("swayam_positions").select("*")

        # Rows that are not his trades never reach this endpoint at all, in
        # any mode, under any filter. This is the fix for the fault that
        # mattered most: round 3 put a win rate on his home page, and nothing
        # anywhere consulted `provenance` before computing it.
        query = query.eq("provenance", LIVE_PROVENANCE)

        if status != "all":
            query = query.eq("status", status)
        else:
            query = query.neq("status", "archived")

        # Paper and real money are two separate books and must never be added
        # together. Home labels the record card "Paper", and a label the API
        # cannot honour is a claim, not a fact.
        if mode != "all":
            query = query.eq("mode", mode)

        if strategy:
            query = query.ilike("strategy_name", f"%{strategy}%")
        if exit_reason:
            query = query.eq("exit_reason", exit_reason)
        if directional_view:
            query = query.eq("directional_view", directional_view)
        if from_date:
            query = query.gte("opened_at", from_date)
        if to_date:
            query = query.lte("opened_at", f"{to_date}T23:59:59")

        res = query.execute()
        raw_positions = res.data or []

        # What the one mark excluded, so the page can say so out loud rather
        # than leaving him to wonder which rows are missing and why.
        excluded_check = (
            client.table("swayam_positions")
            .select("id")
            .neq("provenance", LIVE_PROVENANCE)
            .execute()
        )
        excluded_test_rows = len(excluded_check.data or [])
    except Exception as exc:
        logger.error("Failed to query journal trades from Supabase: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "Journal service unavailable: cannot reach database to query trade history. "
                "This is a safety-critical service — do not assume zero trades during an outage. "
                f"Underlying error: {exc}"
            ),
        ) from exc

    # 2. Query attached lessons in swayam_lessons and history in swayam_trade_history
    lessons_by_pos_id: dict[str, dict[str, Any]] = {}
    try:
        l_res = db.client.table("swayam_lessons").select("*").execute()
        if l_res.data:
            for les in l_res.data:
                lessons_by_pos_id[str(les.get("position_id"))] = les
    except Exception as exc:
        logger.warning("Could not fetch attached lessons: %s", exc)

    history_by_pos_id: dict[str, dict[str, Any]] = {}
    try:
        h_res = db.client.table("swayam_trade_history").select("*").execute()
        if h_res.data:
            for hist in h_res.data:
                history_by_pos_id[str(hist.get("position_id"))] = hist
    except Exception as exc:
        logger.warning("Could not fetch trade history: %s", exc)

    # 3. Post-process, compute KPIs, and apply Python-level filters
    processed_trades: list[JournalTradeItem] = []
    scored_count = 0          # squared-off trades, the only ones the record counts
    unpriced_closed = 0       # closed, but no history row, so the money is unknown
    total_gross_pnl = 0.0
    total_net_pnl = 0.0
    total_charges = 0.0
    wins = 0
    losses = 0
    breakevens = 0
    rules_followed_count = 0
    sum_rr_actual = 0.0
    rr_count = 0
    max_win_item: Optional[dict[str, Any]] = None
    max_loss_item: Optional[dict[str, Any]] = None

    for pos in raw_positions:
        pos_id = str(pos.get("id"))
        p_status = pos.get("status", "closed")
        # `swayam_trade_history` is the only place a squared-off result lives.
        # The old fallback read `realized_pnl_inr` and `unrealized_pnl_inr` off
        # the position row; NEITHER COLUMN EXISTS on `swayam_positions`, so it
        # silently booked zero for every trade without a history row. A trade
        # whose result cannot be read is now unknown, never a flat nothing.
        hist_rec = history_by_pos_id.get(pos_id)
        money_is_known = hist_rec is not None
        if hist_rec:
            net_pnl = float(hist_rec.get("realized_pnl_inr") or 0.0)
            charges = float(hist_rec.get("total_charges_inr") or pos.get("charges_inr") or 0.0)
            gross_pnl = net_pnl + charges
        else:
            net_pnl = 0.0
            charges = 0.0
            gross_pnl = 0.0

        # His rule, given 2026-09-08: "I only want the trade that is squared off
        # to go in as a trade journal." A trade counts towards the record when
        # it is closed AND its result can be read. Everything else is listed but
        # never scored.
        is_squared_off = p_status == "closed" and money_is_known

        # Derive outcome
        if not is_squared_off:
            trade_outcome = "UNKNOWN"
        elif net_pnl > 50.0:
            trade_outcome = "WIN"
        elif net_pnl < -50.0:
            trade_outcome = "LOSS"
        else:
            trade_outcome = "BREAKEVEN"

        # Apply outcome filter
        if outcome != "all" and trade_outcome.lower() != outcome.lower():
            continue

        # Apply discipline filter
        is_followed = pos.get("rules_followed")
        if is_followed is None:
            is_followed = True
        if discipline == "followed" and not is_followed:
            continue
        if discipline == "broken" and is_followed:
            continue

        # R:R calculations
        max_loss = float(pos.get("max_loss_inr") or 0.0)
        max_profit = float(pos.get("max_profit_inr") or 0.0)
        rr_planned = round(max_profit / max_loss, 2) if max_loss > 0 else None
        rr_actual = (
            round(net_pnl / max_loss, 2)
            if (is_squared_off and max_loss > 0 and net_pnl != 0)
            else None
        )

        # Time in trade
        tit_mins = pos.get("time_in_trade_minutes")
        if tit_mins is None and pos.get("opened_at") and pos.get("closed_at"):
            try:
                t_open = datetime.fromisoformat(pos["opened_at"].replace("Z", "+00:00"))
                t_close = datetime.fromisoformat(pos["closed_at"].replace("Z", "+00:00"))
                tit_mins = int((t_close - t_open).total_seconds() / 60)
            except Exception:
                pass

        # Attached lesson
        lesson_data = lessons_by_pos_id.get(pos_id)
        lesson_id = str(lesson_data["id"]) if lesson_data else None
        lesson_text = lesson_data.get("lesson_text") if lesson_data else None
        lesson_source = lesson_data.get("lesson_source") if lesson_data else None

        # Stats accumulation. Only a squared-off trade moves a single figure
        # in his record. An open trade is a live position, not a result, and a
        # closed one whose money cannot be read is a broken record rather than
        # a flat zero.
        if not is_squared_off:
            if p_status == "closed":
                unpriced_closed += 1
        else:
            scored_count += 1
            total_gross_pnl += gross_pnl
            total_net_pnl += net_pnl
            total_charges += charges

            if trade_outcome == "WIN":
                wins += 1
            elif trade_outcome == "LOSS":
                losses += 1
            else:
                breakevens += 1

            if is_followed:
                rules_followed_count += 1

            if rr_actual is not None:
                sum_rr_actual += rr_actual
                rr_count += 1

        # Outliers tracking, over scored trades only
        if is_squared_off and (max_win_item is None or net_pnl > max_win_item["pnl"]):
            max_win_item = {
                "position_id": pos_id,
                "strategy": pos.get("strategy_name", "Spread"),
                "pnl": net_pnl,
                "date": pos.get("opened_at", "")[:10],
            }
        if is_squared_off and (max_loss_item is None or net_pnl < max_loss_item["pnl"]):
            max_loss_item = {
                "position_id": pos_id,
                "strategy": pos.get("strategy_name", "Spread"),
                "pnl": net_pnl,
                "date": pos.get("opened_at", "")[:10],
            }

        item = JournalTradeItem(
            position_id=pos_id,
            opened_at=pos.get("opened_at", ""),
            closed_at=pos.get("closed_at"),
            strategy_name=pos.get("strategy_name", "Spread"),
            underlying=pos.get("underlying", "NIFTY"),
            legs_summary=_format_legs_summary(pos.get("legs", [])),
            entry_debit_credit_inr=float(pos.get("net_debit_credit_inr") or 0.0),
            gross_pnl_inr=round(gross_pnl, 2) if is_squared_off else None,
            net_pnl_inr=round(net_pnl, 2) if is_squared_off else None,
            charges_inr=round(charges, 2) if is_squared_off else None,
            rr_planned=rr_planned,
            rr_actual=rr_actual,
            time_in_trade_str=_format_time_in_trade(tit_mins),
            time_in_trade_minutes=tit_mins,
            points_in_trade=pos.get("points_in_trade"),
            duration_days=round(tit_mins / 1440, 2) if tit_mins else None,
            status=p_status,
            outcome=trade_outcome,
            exit_reason=pos.get("exit_reason"),
            rules_followed=is_followed,
            rules_broken_reason=pos.get("rules_broken_reason"),
            directional_view=pos.get("directional_view"),
            setup_technical=pos.get("setup_technical"),
            setup_location=pos.get("setup_location"),
            with_or_against_trend=pos.get("with_or_against_trend"),
            moneyness_summary=pos.get("moneyness_summary"),
            entry_rationale=pos.get("entry_rationale"),
            exit_rationale=pos.get("exit_rationale"),
            journal_path=pos.get("journal_path"),
            lesson_id=lesson_id,
            lesson_text=lesson_text,
            lesson_source=lesson_source,
        )
        processed_trades.append(item)

    # 4. Sorting
    if sort_by == "date_asc":
        processed_trades.sort(key=lambda t: t.opened_at)
    elif sort_by == "pnl_desc":
        # An unscored trade has no result to sort by; it sinks to the bottom
        # rather than being treated as a zero-rupee trade.
        processed_trades.sort(
            key=lambda t: (t.net_pnl_inr is not None, t.net_pnl_inr or 0.0), reverse=True
        )
    elif sort_by == "pnl_asc":
        processed_trades.sort(
            key=lambda t: (t.net_pnl_inr is None, t.net_pnl_inr or 0.0)
        )
    else:  # date_desc default
        processed_trades.sort(key=lambda t: t.opened_at, reverse=True)

    total_count = len(processed_trades)
    paginated_trades = processed_trades[offset : offset + limit]

    # Every rate below is out of the SQUARED-OFF trades, never out of every row
    # that happened to match the filter. An empty book returns nothing at all
    # rather than a 0% win rate and a 100% discipline rate, both of which read
    # as real figures on his screen.
    win_rate = round((wins / scored_count * 100), 1) if scored_count > 0 else None
    avg_rr = round(sum_rr_actual / rr_count, 2) if rr_count > 0 else None
    disc_rate = (
        round((rules_followed_count / scored_count * 100), 1) if scored_count > 0 else None
    )
    charges_drag_pct = (
        round((total_charges / total_gross_pnl * 100), 1) if total_gross_pnl > 0 else None
    )
    capital_base, capital_source = _capital_base()
    pnl_pct_capital = _pct(total_net_pnl, capital_base) if scored_count > 0 else None

    kpis = JournalKPIs(
        total_trades=scored_count,
        wins_count=wins,
        losses_count=losses,
        breakeven_count=breakevens,
        win_rate_pct=win_rate,
        avg_rr_actual=avg_rr,
        cumulative_net_pnl_inr=round(total_net_pnl, 2),
        cumulative_gross_pnl_inr=round(total_gross_pnl, 2),
        cumulative_pnl_pct_of_capital=pnl_pct_capital,
        discipline_rate_pct=disc_rate,
        charges_drag_inr=round(total_charges, 2),
        charges_drag_pct=charges_drag_pct,
        max_profit_trade=max_win_item,
        max_loss_trade=max_loss_item,
    )

    return JournalTradesResponse(
        trades=paginated_trades,
        total_count=total_count,
        kpis=kpis,
        excluded_test_rows=excluded_test_rows,
        unpriced_closed_trades=unpriced_closed,
        capital_base_inr=capital_base,
        capital_base_source=capital_source,
    )


@router.post("/api/journal/archive-test-trades", response_model=ArchiveTestTradesResponse)
def archive_test_trades() -> ArchiveTestTradesResponse:
    """RETIRED 2026-09-08. Kept as a 410 so an old cached page cannot write.

    This endpoint archived every paper position opened before a hardcoded date
    of 2026-09-06, and the Trade Journal page fired it on first load with
    nothing clicked. That was two faults at once: a database write triggered by
    opening a page, and a SECOND mark for "this is not a real trade" that could
    disagree with `provenance`.

    There is one mark now. `provenance` is filtered in every query in this file
    and the count of what it excluded is returned, so the page can show him
    which rows are left out and why. Nothing needs archiving by date.

    A browser still holding the old bundle will call this. It must not write.
    """
    raise HTTPException(
        status_code=410,
        detail=(
            "Archiving by date is retired. A row is excluded from the record by "
            "its `provenance` column, which every journal query now filters, and "
            "the number of excluded rows is reported with the trades. Reload the "
            "page to pick up the current version."
        ),
    )


@router.get("/api/journal/trade/{position_id}")
def get_journal_trade_detail(position_id: str) -> dict[str, Any]:
    """Returns comprehensive trade inspection detail including legs, payoff, lesson, and rationale."""
    try:
        res = db.client.table("swayam_positions").select("*").eq("id", position_id).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail=f"Position #{position_id} not found")
        trade = res.data[0]
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to query trade %s from Supabase: %s", position_id, exc)
        raise HTTPException(
            status_code=503,
            detail=f"Database error reading trade details: {exc}",
        ) from exc

    # Fetch attached lesson and history
    lesson = None
    try:
        l_res = db.client.table("swayam_lessons").select("*").eq("position_id", position_id).execute()
        if l_res.data:
            lesson = l_res.data[0]
    except Exception as exc:
        logger.warning("Could not fetch lesson for trade %s: %s", position_id, exc)

    hist_rec = None
    try:
        h_res = db.client.table("swayam_trade_history").select("*").eq("position_id", position_id).execute()
        if h_res.data:
            hist_rec = h_res.data[0]
    except Exception as exc:
        logger.warning("Could not fetch history for trade %s: %s", position_id, exc)

    net_pnl = float(hist_rec.get("realized_pnl_inr", 0.0)) if hist_rec else float(trade.get("realized_pnl_inr") or trade.get("unrealized_pnl_inr") or 0.0)

    return {
        "position": trade,
        "position_id": position_id,
        "strategy_name": trade.get("strategy_name", "Options Trade"),
        "net_pnl_inr": net_pnl,
        "lesson": lesson,
        "lesson_text": lesson.get("lesson_text") if lesson else None,
        "legs": trade.get("legs", []),
        "journal_path": trade.get("journal_path"),
    }


@router.get("/api/journal/analytics")
def get_journal_analytics(
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    """Returns edge analytics: cumulative P&L curve, P&L by strategy, by exit reason, and by trend."""
    try:
        # This query had NO filter of any kind beyond the dates, so every one of
        # the 81 build-test rows fed the cumulative curve, the drawdown, the
        # expectancy and every per-strategy figure below it. Two filters now:
        # his rows only, and squared-off trades only.
        query = (
            db.client.table("swayam_positions")
            .select("*")
            .eq("provenance", LIVE_PROVENANCE)
            .eq("status", "closed")
        )
        if from_date:
            query = query.gte("opened_at", from_date)
        if to_date:
            query = query.lte("opened_at", f"{to_date}T23:59:59")
        res = query.execute()
        trades = res.data or []
    except Exception as exc:
        logger.error("Analytics fetch failed from Supabase: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"Analytics service unavailable: cannot reach database. Error: {exc}",
        ) from exc

    # Query trade history for accurate realized P&L
    history_by_pos_id: dict[str, dict[str, Any]] = {}
    try:
        h_res = db.client.table("swayam_trade_history").select("*").execute()
        if h_res.data:
            for hist in h_res.data:
                history_by_pos_id[str(hist.get("position_id"))] = hist
    except Exception as exc:
        logger.warning("Could not fetch trade history for analytics: %s", exc)

    # Query recent lessons for Lesson Ledger scroll
    recent_lessons: list[dict[str, Any]] = []
    try:
        les_res = db.client.table("swayam_lessons").select("*").order("created_at", desc=True).limit(10).execute()
        recent_lessons = les_res.data or []
    except Exception as exc:
        logger.warning("Could not fetch recent lessons for analytics: %s", exc)

    # Sort chronologically for cumulative series
    sorted_trades = sorted(trades, key=lambda t: t.get("opened_at") or "")

    cum_pnl = 0.0
    series: list[dict[str, Any]] = []
    by_strategy: dict[str, dict[str, Any]] = {}
    by_exit_reason: dict[str, dict[str, Any]] = {}
    by_direction: dict[str, dict[str, Any]] = {}
    by_trend: dict[str, dict[str, Any]] = {
        "With": {"trades": 0, "wins": 0, "pnl": 0.0},
        "Against": {"trades": 0, "wins": 0, "pnl": 0.0},
        "Middle": {"trades": 0, "wins": 0, "pnl": 0.0},
    }

    total_mins = 0
    valid_duration_count = 0
    running_max_pnl = 0.0
    max_drawdown = 0.0

    scored_trades = 0
    unpriced_closed = 0

    for t in sorted_trades:
        t_id = str(t.get("id"))
        hist_rec = history_by_pos_id.get(t_id)
        if hist_rec is None:
            # Same silent zero as the trades endpoint had: the two column names
            # this used to fall back to do not exist on swayam_positions, so
            # every trade without a history row was scored as a flat nothing.
            # It is left out and counted instead.
            unpriced_closed += 1
            continue
        net_pnl = float(hist_rec.get("realized_pnl_inr") or 0.0)
        scored_trades += 1
        cum_pnl += net_pnl
        trade_date = (t.get("opened_at") or "")[:10]
        series.append({"date": trade_date, "cumulative_pnl_inr": round(cum_pnl, 2)})

        # Drawdown calculation
        if cum_pnl > running_max_pnl:
            running_max_pnl = cum_pnl
        dd = cum_pnl - running_max_pnl
        if dd < max_drawdown:
            max_drawdown = dd

        # Strategy grouping
        strat = t.get("strategy_name") or "Custom"
        if strat not in by_strategy:
            by_strategy[strat] = {"strategy": strat, "trades": 0, "pnl_inr": 0.0, "wins": 0}
        by_strategy[strat]["trades"] += 1
        by_strategy[strat]["pnl_inr"] = round(by_strategy[strat]["pnl_inr"] + net_pnl, 2)
        if net_pnl > 0:
            by_strategy[strat]["wins"] += 1

        # Exit Reason grouping
        reason = t.get("exit_reason") or "unspecified"
        if reason not in by_exit_reason:
            by_exit_reason[reason] = {"exit_reason": reason, "trades": 0, "pnl_inr": 0.0, "wins": 0}
        by_exit_reason[reason]["trades"] += 1
        by_exit_reason[reason]["pnl_inr"] = round(by_exit_reason[reason]["pnl_inr"] + net_pnl, 2)
        if net_pnl > 0:
            by_exit_reason[reason]["wins"] += 1

        # Direction grouping
        dir_view = t.get("directional_view") or "Neutral"
        if dir_view not in by_direction:
            by_direction[dir_view] = {"directional_view": dir_view, "trades": 0, "pnl_inr": 0.0}
        by_direction[dir_view]["trades"] += 1
        by_direction[dir_view]["pnl_inr"] = round(by_direction[dir_view]["pnl_inr"] + net_pnl, 2)

        # Trend alignment grouping
        trend = t.get("with_or_against_trend") or "With"
        if trend in by_trend:
            by_trend[trend]["trades"] += 1
            by_trend[trend]["pnl"] += net_pnl
            if net_pnl > 0:
                by_trend[trend]["wins"] += 1

        # Duration
        mins = t.get("time_in_trade_minutes")
        if mins:
            total_mins += mins
            valid_duration_count += 1

    # Strategy win rate calculation
    strat_list = []
    for s in by_strategy.values():
        s["win_rate_pct"] = round((s["wins"] / s["trades"] * 100), 1) if s["trades"] > 0 else 0.0
        strat_list.append(s)

    # Exit reason win rate calculation
    exit_list = []
    for e in by_exit_reason.values():
        e["win_rate_pct"] = round((e["wins"] / e["trades"] * 100), 1) if e["trades"] > 0 else 0.0
        exit_list.append(e)

    # Trend stats calculation
    trend_stats = {}
    for k, v in by_trend.items():
        # A trend he has never traded has no win rate. It used to report 0.0%,
        # which reads as "you lost every one of them".
        wr = round((v["wins"] / v["trades"] * 100), 1) if v["trades"] > 0 else None
        trend_stats[k] = {"trades": v["trades"], "win_rate_pct": wr, "pnl_inr": round(v["pnl"], 2)}

    avg_duration_days = (
        round(total_mins / valid_duration_count / 1440, 1) if valid_duration_count > 0 else None
    )
    expectancy = round(cum_pnl / scored_trades, 2) if scored_trades else None
    capital_base, capital_source = _capital_base()

    return {
        "cumulative_pnl_series": series,
        "pnl_by_strategy": strat_list,
        "pnl_by_exit_reason": exit_list,
        "pnl_by_directional_view": list(by_direction.values()),
        "win_rate_by_trend": trend_stats,
        "avg_duration_days": avg_duration_days if scored_trades else None,
        "max_drawdown_inr": round(max_drawdown, 2) if scored_trades else None,
        "max_drawdown_pct_of_capital": (
            _pct(max_drawdown, capital_base) if scored_trades else None
        ),
        "expectancy_per_trade_inr": expectancy,
        "scored_trades": scored_trades,
        "unpriced_closed_trades": unpriced_closed,
        "capital_base_inr": capital_base,
        "capital_base_source": capital_source,
        "recent_lessons": recent_lessons,
    }
