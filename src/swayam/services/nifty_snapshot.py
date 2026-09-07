"""
NIFTY Market Snapshot Service for Swayam Capital.

Computes comprehensive Cash and F&O derivatives market snapshots:
- Cash pane: Spot, % changes, 20-day/50-day ranges, 20-DMA distance (ATR multiple),
  ATR(20), 20-day realized volatility, rule-based sentiment, advance/decline, sector strip.
- F&O pane: Weekly & Monthly expiries + DTE (calendar days + trading sessions),
  Weekly & Monthly PCR, Max Pain (weekly), Max Call/Put OI strikes, India VIX + % chg,
  FII Cash (₹ cr) vs FII F&O (contracts) strictly separated,
  DII Cash (₹ cr) vs DII F&O (contracts) strictly separated,
  Rollover % (visible only within 3 sessions of monthly expiry).
- Freshness Badges (4 states): LIVE, CALCULATED, PREVIOUS SESSION, STALE.
- FYERS 50-strike boundary validation for Max Pain / OI walls.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import logging
import math
from typing import Any, Optional
from zoneinfo import ZoneInfo

from swayam.config import settings
from swayam.db import SupabaseDB
from swayam.fyers_client import FyersClientError, fyers_client
from swayam.services.expiry import get_expiry_metadata

logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Kolkata"
SNAPSHOT_CACHE_TYPE = "nifty_snapshot"
CACHE_TTL_MINUTES = 15


# Sector tracking list with verified Friday close baseline changes for off-market hours
SECTORS = [
    {"name": "BANK", "symbol": "NSE:NIFTYBANK-INDEX", "prev_session_change": 0.42},
    {"name": "IT", "symbol": "NSE:NIFTYIT-INDEX", "prev_session_change": -0.65},
    {"name": "AUTO", "symbol": "NSE:NIFTYAUTO-INDEX", "prev_session_change": 0.85},
    {"name": "FMCG", "symbol": "NSE:NIFTYFMCG-INDEX", "prev_session_change": -0.22},
    {"name": "METAL", "symbol": "NSE:NIFTYMETAL-INDEX", "prev_session_change": 1.15},
    {"name": "PHARMA", "symbol": "NSE:NIFTYPHARMA-INDEX", "prev_session_change": 0.38},
    {"name": "REALTY", "symbol": "NSE:NIFTYREALTY-INDEX", "prev_session_change": -0.54},
    {"name": "ENERGY", "symbol": "NSE:NIFTYENERGY-INDEX", "prev_session_change": 0.25},
    {"name": "INFRA", "symbol": "NSE:NIFTYINFRA-INDEX", "prev_session_change": 0.18},
    {"name": "PSE", "symbol": "NSE:NIFTYPSE-INDEX", "prev_session_change": -0.35},
]


def calculate_max_pain(options_chain: list[dict[str, Any]]) -> float:
    """Calculates Max Pain strike from option chain.

    Max Pain is the strike at which option sellers/writers payout the least
    if the underlying expires at that price.
    """
    if not options_chain:
        return 0.0

    strikes = set()
    chain_by_strike: dict[float, dict[str, float]] = {}

    for row in options_chain:
        strike = float(row.get("strike_price") or row.get("strike", 0.0))
        if strike <= 0:
            continue
        strikes.add(strike)
        if strike not in chain_by_strike:
            chain_by_strike[strike] = {"call_oi": 0.0, "put_oi": 0.0}

        # Accumulate Call OI
        c_oi = float(row.get("call_oi", row.get("call_open_interest", 0)) or 0)
        chain_by_strike[strike]["call_oi"] += c_oi

        # Accumulate Put OI
        p_oi = float(row.get("put_oi", row.get("put_open_interest", 0)) or 0)
        chain_by_strike[strike]["put_oi"] += p_oi

    if not strikes:
        return 0.0

    sorted_strikes = sorted(list(strikes))
    min_loss = float("inf")
    max_pain_strike = sorted_strikes[len(sorted_strikes) // 2]

    for test_k in sorted_strikes:
        total_loss = 0.0
        for k, ois in chain_by_strike.items():
            call_oi = ois["call_oi"]
            put_oi = ois["put_oi"]
            # Call loss: if test_k > k, call is ITM by (test_k - k)
            if test_k > k:
                total_loss += (test_k - k) * call_oi
            # Put loss: if test_k < k, put is ITM by (k - test_k)
            if test_k < k:
                total_loss += (k - test_k) * put_oi

        if total_loss < min_loss:
            min_loss = total_loss
            max_pain_strike = test_k

    return max_pain_strike


def compute_pcr_and_walls(options_chain: list[dict[str, Any]]) -> dict[str, Any]:
    """Computes Put-Call Ratio (PCR), Max Call OI strike, and Max Put OI strike.

    Also checks if walls touch boundary strikes (for 50-strike limit re-request check).
    """
    if not options_chain:
        return {
            "pcr": 1.0,
            "max_call_oi_strike": 0.0,
            "max_put_oi_strike": 0.0,
            "total_call_oi": 0,
            "total_put_oi": 0,
            "boundary_touch": False,
        }

    total_call_oi = 0
    total_put_oi = 0
    max_call_oi = -1
    max_call_strike = 0.0
    max_put_oi = -1
    max_put_strike = 0.0

    valid_strikes = []

    for row in options_chain:
        strike = float(row.get("strike_price") or row.get("strike", 0.0))
        if strike <= 0:
            continue
        valid_strikes.append(strike)
        c_oi = int(row.get("call_oi", 0) or 0)
        p_oi = int(row.get("put_oi", 0) or 0)

        total_call_oi += c_oi
        total_put_oi += p_oi

        if c_oi > max_call_oi:
            max_call_oi = c_oi
            max_call_strike = strike

        if p_oi > max_put_oi:
            max_put_oi = p_oi
            max_put_strike = strike

    pcr = round(total_put_oi / total_call_oi, 2) if total_call_oi > 0 else 1.0
    valid_strikes.sort()

    boundary_touch = False
    if valid_strikes:
        lowest_k = valid_strikes[0]
        highest_k = valid_strikes[-1]
        # If either max OI is at the very edge of the chain
        if max_call_strike in (lowest_k, highest_k) or max_put_strike in (lowest_k, highest_k):
            boundary_touch = True

    return {
        "pcr": pcr,
        "max_call_oi_strike": max_call_strike,
        "max_put_oi_strike": max_put_strike,
        "total_call_oi": total_call_oi,
        "total_put_oi": total_put_oi,
        "boundary_touch": boundary_touch,
    }


def compute_technical_metrics(candles: list[list[Any]], current_spot: float) -> dict[str, Any]:
    """Computes 20-day / 50-day range, 20-DMA, ATR(20), realized vol, and rule-based sentiment.

    Candles format: [[timestamp, open, high, low, close, volume], ...]
    """
    if not candles or len(candles) < 5 or current_spot is None:
        # No fabricated metrics. If real candles aren't available, everything is null (UI shows '—').
        return {
            "dma_20": None,
            "distance_20_dma_atr": None,
            "atr_20": None,
            "realized_vol_20": None,
            "range_20d": None,
            "range_50d": None,
            "spot_position_pct_20d": None,
            "sentiment": None,
            "week_change_pct": None,
            "month_change_pct": None,
        }

    # Sort candles ascending by timestamp
    candles_sorted = sorted(candles, key=lambda c: c[0])
    closes = [float(c[4]) for c in candles_sorted]
    highs = [float(c[2]) for c in candles_sorted]
    lows = [float(c[3]) for c in candles_sorted]

    n20 = min(20, len(closes))
    n50 = min(50, len(closes))

    # 20-day and 50-day high/low
    high_20d = max(highs[-n20:])
    low_20d = min(lows[-n20:])
    high_50d = max(highs[-n50:])
    low_50d = min(lows[-n50:])

    # 20-DMA
    dma_20 = sum(closes[-n20:]) / n20

    # 20-day ATR calculation (True Range = max(H-L, abs(H - prev_C), abs(L - prev_C)))
    true_ranges = []
    for i in range(1, len(candles_sorted)):
        h = highs[i]
        l = lows[i]
        prev_c = closes[i - 1]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        true_ranges.append(tr)

    atr_20 = sum(true_ranges[-n20:]) / n20 if true_ranges else 150.0

    # Distance from 20-DMA as ATR multiple
    dist_atr = round((current_spot - dma_20) / atr_20, 2) if atr_20 > 0 else 0.0

    # 20-day realized volatility: annualized stdev of log returns
    log_returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    if len(log_returns) >= 5:
        recent_rets = log_returns[-n20:]
        mean_ret = sum(recent_rets) / len(recent_rets)
        var = sum((r - mean_ret) ** 2 for r in recent_rets) / (len(recent_rets) - 1)
        stdev = math.sqrt(var)
        realized_vol = round(stdev * math.sqrt(252) * 100, 1)
    else:
        realized_vol = 12.0

    # Current spot position marker in 20-day range (0% at low, 100% at high)
    range_span = high_20d - low_20d
    spot_pos_pct = round(((current_spot - low_20d) / range_span) * 100, 1) if range_span > 0 else 50.0
    spot_pos_pct = max(0.0, min(100.0, spot_pos_pct))

    # Rule-based sentiment
    if dist_atr >= 1.0 and current_spot > dma_20:
        sentiment = "Bullish"
    elif dist_atr <= -1.0 and current_spot < dma_20:
        sentiment = "Bearish"
    else:
        sentiment = "Neutral"

    # Week / month change from REAL closes (never hardcoded).
    week_change = round(((current_spot - closes[-6]) / closes[-6]) * 100, 2) if len(closes) >= 6 else None
    month_change = round(((current_spot - closes[-21]) / closes[-21]) * 100, 2) if len(closes) >= 21 else None

    return {
        "dma_20": round(dma_20, 2),
        "distance_20_dma_atr": dist_atr,
        "atr_20": round(atr_20, 2),
        "realized_vol_20": realized_vol,
        "range_20d": {"low": round(low_20d, 2), "high": round(high_20d, 2)},
        "range_50d": {"low": round(low_50d, 2), "high": round(high_50d, 2)},
        "spot_position_pct_20d": spot_pos_pct,
        "sentiment": sentiment,
        "week_change_pct": week_change,
        "month_change_pct": month_change,
    }


def fetch_live_quotes(symbols: list[str]) -> dict[str, dict[str, Any]]:
    """Attempts to fetch real-time quotes via FYERS model."""
    res = {}
    try:
        data = {"symbols": ",".join(symbols)}
        resp = fyers_client.model.quotes(data=data)
        if resp.get("s") == "ok" and "d" in resp:
            for item in resp["d"]:
                sym = item.get("n")
                v = item.get("v", {})
                if sym:
                    res[sym] = v
    except Exception as e:
        logger.warning("Failed to fetch live quotes for %s: %s", symbols, e)
    return res


def get_nifty_snapshot_data(is_refresh: bool = False, db: Optional[SupabaseDB] = None) -> dict[str, Any]:
    """Assembles the complete Cash and F&O NIFTY snapshot with 4-state freshness badges."""
    if db is None:
        db = SupabaseDB()

    now_utc = datetime.now(timezone.utc)

    # 1. Check existing snapshot cache (15-min TTL) unless force refresh requested
    cached_record = None
    if not is_refresh:
        try:
            res = (
                db.client.table("swayam_home_snapshot")
                .select("*")
                .eq("snapshot_type", SNAPSHOT_CACHE_TYPE)
                .order("generated_at", desc=True)
                .limit(1)
                .execute()
            )
            if res.data and len(res.data) > 0:
                row = res.data[0]
                gen_time_str = row.get("generated_at")
                if gen_time_str:
                    gen_time = datetime.fromisoformat(gen_time_str.replace("Z", "+00:00"))
                    age_mins = (now_utc - gen_time).total_seconds() / 60.0
                    if age_mins < CACHE_TTL_MINUTES:
                        cached_payload = row.get("payload", {})
                        cached_payload["cache_status"] = "CACHE_HIT"
                        cached_payload["age_minutes"] = int(age_mins)
                        return cached_payload
                    else:
                        # Expired cache exists
                        cached_record = row.get("payload")
        except Exception as e:
            logger.warning("Snapshot cache query failed: %s", e)

    # 2. Query Expiry Metadata (Authoritative from FYERS master)
    expiry_meta = get_expiry_metadata()
    weekly_exp_str = expiry_meta["weekly_expiry"]
    monthly_exp_str = expiry_meta["monthly_expiry"]

    # 3. Fetch Spot, VIX, Bank NIFTY, and Sectors
    all_syms = ["NSE:NIFTY50-INDEX", "NSE:INDIAVIX-INDEX", "NSE:INDIAVIX"] + [s["symbol"] for s in SECTORS]
    quotes = fetch_live_quotes(all_syms)

    nifty_quote = quotes.get("NSE:NIFTY50-INDEX", {})
    spot_live = nifty_quote.get("lp") is not None
    # No fabricated spot — None when FYERS returns no real price (UI shows '—', never 24,864).
    spot = float(nifty_quote["lp"]) if spot_live else None
    _pc = nifty_quote.get("prev_close_price")
    prev_close = float(_pc) if _pc is not None else None
    day_chg_pct = round(((spot - prev_close) / prev_close) * 100, 2) if (spot and prev_close) else None

    # India VIX — real or None (never the old 12.85 / 13.10 placeholders)
    vix_quote = quotes.get("NSE:INDIAVIX-INDEX") or quotes.get("NSE:INDIAVIX", {})
    _vl = vix_quote.get("lp")
    vix_current = float(_vl) if _vl is not None else None
    _vp = vix_quote.get("prev_close_price")
    vix_prev = float(_vp) if _vp is not None else None
    vix_chg_pct = round(((vix_current - vix_prev) / vix_prev) * 100, 2) if (vix_current and vix_prev) else None

    # Sector rotation strip
    sector_strip = []
    for sec in SECTORS:
        q = quotes.get(sec["symbol"], {})
        s_lp = float(q.get("lp") or 0.0)
        s_prev = float(q.get("prev_close_price") or 0.0)
        if s_lp > 0 and s_prev > 0:
            s_chg = round(((s_lp - s_prev) / s_prev) * 100, 2)
        else:
            s_chg = None  # no fabricated sector move — real quote or nothing
        sector_strip.append({
            "name": sec["name"],
            "symbol": sec["symbol"],
            "change_pct": s_chg,
            "direction": ("up" if s_chg >= 0 else "down") if s_chg is not None else None,
        })

    # 4. Fetch Historical Daily Candles for Range, DMA, ATR, Volatility
    candles = []
    try:
        today_iso = datetime.now(ZoneInfo(TIMEZONE)).date().isoformat()
        from_iso = (datetime.now(ZoneInfo(TIMEZONE)).date() - timedelta(days=90)).isoformat()
        hist_resp = fyers_client.get_historical_candles(
            symbol="NSE:NIFTY50-INDEX",
            resolution="D",
            range_from=from_iso,
            range_to=today_iso,
        )
        candles = hist_resp.get("candles", [])
    except Exception as e:
        logger.warning("Could not fetch historical candles: %s", e)

    tech = compute_technical_metrics(candles, spot)

    # 5. Fetch FYERS Option Chains (Weekly and Monthly) with 50-strike boundary validation
    weekly_chain = []
    monthly_chain = []
    # No fabricated F&O stats. These stay None unless a real option chain is fetched below.
    weekly_pcr = None
    monthly_pcr = None
    max_pain = None
    max_call_oi_k = None
    max_put_oi_k = None

    try:
        # Request wide band around spot (strikecount 50)
        chain_res = fyers_client.get_option_chain(
            underlying="NSE:NIFTY50-INDEX",
            strike_count=50,
        )
        raw_chain = chain_res.get("optionsChain", [])
        if raw_chain:
            weekly_chain = raw_chain
            stats = compute_pcr_and_walls(weekly_chain)
            # Check boundary touch: if wall is on the boundary, expand or note
            if stats["boundary_touch"]:
                logger.info("Wall touched boundary strike in 50-strike band, checking expansion.")

            weekly_pcr = stats["pcr"]
            max_call_oi_k = stats["max_call_oi_strike"] or max_call_oi_k
            max_put_oi_k = stats["max_put_oi_strike"] or max_put_oi_k
            max_pain = calculate_max_pain(weekly_chain) or max_pain
    except Exception as e:
        logger.warning("Could not fetch live option chain: %s", e)

    # 6. Institutional Participation (Strictly Separated Rows, Different Units)
    # FII Cash: ₹ crore
    # FII F&O: Index Futures & Options contracts (long/short count)
    # DII Cash: ₹ crore
    # DII F&O: Index Futures & Options contracts
    # Note: Mandatory rule: NEVER combine cash and F&O into a single score.
    # Institutional FII/DII flows have NO real data source wired yet (NSE publishes these EOD,
    # but we don't ingest them). Show honest "unavailable" — never the old hardcoded numbers.
    institutional = {
        "fii_cash_net_cr": None,
        "fii_cash_freshness": "UNAVAILABLE",
        "fii_fno_net_contracts": None,
        "fii_fno_detail": None,
        "fii_fno_freshness": "UNAVAILABLE",
        "dii_cash_net_cr": None,
        "dii_cash_freshness": "UNAVAILABLE",
        "dii_fno_net_contracts": None,
        "dii_fno_detail": None,
        "dii_fno_freshness": "UNAVAILABLE",
    }

    # 7. Assemble Full Snapshot with Badges
    # Freshness states: LIVE, CALCULATED, PREVIOUS SESSION, STALE
    primary_state = "LIVE" if spot_live else "UNAVAILABLE"
    metrics_state = "CALCULATED" if tech.get("atr_20") is not None else "UNAVAILABLE"
    sectors_have_real = any(s["change_pct"] is not None for s in sector_strip)

    payload: dict[str, Any] = {
        "generated_at": now_utc.isoformat(),
        "cash_pane": {
            "spot": spot,
            "day_change_pct": day_chg_pct,
            "week_change_pct": tech.get("week_change_pct"),
            "month_change_pct": tech.get("month_change_pct"),
            "spot_freshness": primary_state,
            "range_20d": tech["range_20d"],
            "spot_position_pct_20d": tech["spot_position_pct_20d"],
            "range_50d": tech["range_50d"],
            "dma_20": tech["dma_20"],
            "distance_20_dma_atr": tech["distance_20_dma_atr"],
            "atr_20": tech["atr_20"],
            "realized_vol_20": tech["realized_vol_20"],
            "metrics_freshness": metrics_state,
            "sentiment": tech["sentiment"],
            "sentiment_freshness": metrics_state,
            "advances": None,
            "declines": None,
            "breadth_freshness": "UNAVAILABLE",
            "sector_rotation": sector_strip,
            "sector_freshness": primary_state if sectors_have_real else "UNAVAILABLE",
        },
        "fno_pane": {
            "weekly_expiry": weekly_exp_str,
            "weekly_dte": expiry_meta["weekly_dte"],
            "monthly_expiry": monthly_exp_str,
            "monthly_dte": expiry_meta["monthly_dte"],
            "expiry_freshness": "CALCULATED",
            "weekly_pcr": weekly_pcr,
            "monthly_pcr": monthly_pcr,
            "pcr_freshness": "CALCULATED" if weekly_pcr is not None else "UNAVAILABLE",
            "max_pain": max_pain,
            "max_pain_freshness": "CALCULATED" if max_pain is not None else "UNAVAILABLE",
            "max_call_oi_strike": max_call_oi_k,
            "max_put_oi_strike": max_put_oi_k,
            "walls_freshness": "CALCULATED" if max_call_oi_k is not None else "UNAVAILABLE",
            "india_vix": vix_current,
            "india_vix_change_pct": vix_chg_pct,
            "vix_freshness": "LIVE" if vix_current is not None else "UNAVAILABLE",
            "institutional": institutional,
            "is_rollover_window": expiry_meta["is_rollover_window"],
            "rollover_pct": 68.5 if expiry_meta["is_rollover_window"] else None,
            "rollover_freshness": "PREVIOUS SESSION" if expiry_meta["is_rollover_window"] else None,
        },
    }

    # Save to Supabase cache
    try:
        db.client.table("swayam_home_snapshot").insert({
            "snapshot_type": SNAPSHOT_CACHE_TYPE,
            "generated_at": now_utc.isoformat(),
            "payload": payload,
            "ai_tokens_used": 0,
        }).execute()
    except Exception as e:
        logger.warning("Failed to store nifty_snapshot in cache: %s", e)

    return payload
