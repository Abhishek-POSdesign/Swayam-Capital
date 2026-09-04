"""
Live market data endpoints for Swayam Capital.

Interacts with FYERS API v3 to provide live NIFTY index spot quotes and
full option chains with in-memory caching to respect rate limits.

BUILD-9-FIXES-A additions:
  GET /api/market/nifty/candles?timeframe=15m|1h|1d  — for interactive chart tabs
  GET /api/market/vix/history?days=N                 — for VIX percentile band
"""

from datetime import datetime, timedelta, timezone
import time
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query
from swayam.api.models_api import OptionChainResponse, StrikeQuote, StrikeRow
from swayam.fyers_client import fyers_client
from swayam.db import db
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory caches
_spot_cache: dict[str, Any] = {"data": None, "timestamp": 0.0}
_chain_cache: dict[str, Any] = {}
_candle_cache: dict[str, Any] = {}   # keyed by timeframe
_vix_cache: dict[str, Any] = {"data": None, "timestamp": 0.0}

# Candle cache TTL in seconds by timeframe
_CANDLE_TTL = {"15m": 60, "1h": 300, "1d": 900}


@router.get("/api/nifty/spot")
def get_nifty_spot() -> dict[str, Any]:
    """Returns current NIFTY 50 spot price with 3-second caching.

    Raises:
        HTTPException(503): If FYERS connection or authentication fails.
    """
    now = time.time()
    if _spot_cache["data"] is not None and (now - _spot_cache["timestamp"]) < 3.0:
        return _spot_cache["data"]

    try:
        spot_price = fyers_client.get_nifty_spot()
        result = {
            "spot": spot_price,
            "as_of": datetime.now(timezone.utc).isoformat(),
        }
        _spot_cache["data"] = result
        _spot_cache["timestamp"] = now
        return result
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"FYERS market data service unavailable or unauthenticated: {e}",
        ) from e


@router.get("/api/option-chain", response_model=OptionChainResponse)
def get_option_chain(
    expiry: str = Query(..., description="Expiration date in YYYY-MM-DD format"),
    strike_count: int = Query(default=20, ge=4, le=50, description="Strikes around ATM"),
) -> OptionChainResponse:
    """Returns option chain snapshot with 5-second caching.

    Raises:
        HTTPException(503): If FYERS is unavailable.
    """
    cache_key = f"{expiry}_{strike_count}"
    now = time.time()

    if cache_key in _chain_cache:
        entry = _chain_cache[cache_key]
        if (now - entry["timestamp"]) < 5.0:
            return entry["data"]

    try:
        raw_chain = fyers_client.get_option_chain(symbol="NSE:NIFTY50-INDEX", expiry=expiry)
        # Parse and format into OptionChainResponse
        spot = raw_chain.get("spot", 25000.0)
        strikes_raw = raw_chain.get("strikes", [])

        strike_rows: list[StrikeRow] = []
        for s in strikes_raw:
            strike_rows.append(
                StrikeRow(
                    strike=s["strike"],
                    ce=StrikeQuote(
                        ltp=s["ce"]["ltp"],
                        iv=s["ce"].get("iv", 0.15),
                        oi=s["ce"].get("oi", 0),
                    ),
                    pe=StrikeQuote(
                        ltp=s["pe"]["ltp"],
                        iv=s["pe"].get("iv", 0.15),
                        oi=s["pe"].get("oi", 0),
                    ),
                )
            )

        response = OptionChainResponse(
            underlying="NIFTY",
            expiry=expiry,
            spot=spot,
            strikes=strike_rows,
        )
        _chain_cache[cache_key] = {"data": response, "timestamp": now}
        return response
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch option chain from FYERS: {e}",
        ) from e


@router.get("/api/market/nifty/candles")
def get_nifty_candles(
    timeframe: str = Query(default="1d", description="Candle timeframe: 15m, 1h, or 1d"),
) -> dict[str, Any]:
    """Returns NIFTY 50 candlestick data for the requested timeframe.

    Data source: FYERS historical API.
    Cached per-timeframe with TTL: 15m→60s, 1h→300s, 1d→900s.

    Returns:
        dict with keys: timeframe, dates, open, high, low, close, ema20, support_levels, resistance_levels
    """
    tf = timeframe.lower()
    if tf not in ("15m", "1h", "1d"):
        raise HTTPException(
            status_code=400,
            detail="Invalid timeframe. Use one of: 15m, 1h, 1d",
        )

    now = time.time()
    ttl = _CANDLE_TTL[tf]
    cache_entry = _candle_cache.get(tf)
    if cache_entry and (now - cache_entry["timestamp"]) < ttl:
        return cache_entry["data"]

    # Map UI timeframe labels to FYERS resolution codes
    fyers_resolution_map = {"15m": "15", "1h": "60", "1d": "D"}
    fyers_resolution = fyers_resolution_map[tf]

    # Lookback periods
    lookback_days = {"15m": 5, "1h": 20, "1d": 45}
    days_back = lookback_days[tf]

    try:
        from_dt = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
        to_dt = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        raw = fyers_client.get_historical_candles(
            symbol="NSE:NIFTY50-INDEX",
            resolution=fyers_resolution,
            date_format="1",
            range_from=from_dt,
            range_to=to_dt,
            cont_flag="1",
        )

        candles = raw.get("candles", [])
        if not candles:
            raise HTTPException(
                status_code=503,
                detail=f"FYERS returned no candle data for timeframe={tf}. Market may be closed or access token expired.",
            )

        dates, opens, highs, lows, closes = [], [], [], [], []
        for c in candles:
            ts, o, h, l, cl = c[0], c[1], c[2], c[3], c[4]
            # FYERS returns epoch seconds for intraday, date string for daily
            if isinstance(ts, (int, float)):
                d = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:00")
            else:
                d = str(ts)
            dates.append(d)
            opens.append(round(o, 2))
            highs.append(round(h, 2))
            lows.append(round(l, 2))
            closes.append(round(cl, 2))

        # Compute 20-period EMA
        ema20 = _compute_ema(closes, 20)

        # Support/resistance: use recent swing low/high within visible window
        visible_lows = lows[-30:] if len(lows) >= 30 else lows
        visible_highs = highs[-30:] if len(highs) >= 30 else highs
        support = round(min(visible_lows), 2) if visible_lows else None
        resistance = round(max(visible_highs), 2) if visible_highs else None

        result: dict[str, Any] = {
            "timeframe": tf,
            "dates": dates,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "ema20": ema20,
            "support_levels": [{"price": support, "label": f"S: {support:,.0f}"}] if support else [],
            "resistance_levels": [{"price": resistance, "label": f"R: {resistance:,.0f}"}] if resistance else [],
            "as_of": datetime.now(timezone.utc).isoformat(),
        }
        _candle_cache[tf] = {"data": result, "timestamp": now}
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"FYERS historical data unavailable for NIFTY ({tf}): {e}",
        ) from e


def _compute_ema(values: list[float], period: int) -> list[float | None]:
    """Compute Exponential Moving Average (EMA) for a list of values.
    Returns None for positions before enough data exists for the period."""
    if len(values) < period:
        return [None] * len(values)
    k = 2.0 / (period + 1)
    ema: list[float | None] = [None] * (period - 1)
    ema_val = sum(values[:period]) / period
    ema.append(round(ema_val, 2))
    for v in values[period:]:
        ema_val = v * k + ema_val * (1 - k)
        ema.append(round(ema_val, 2))
    return ema


@router.get("/api/market/vix/history")
def get_vix_history(
    days: int = Query(default=365, ge=30, le=730, description="Number of calendar days of VIX history to return"),
) -> dict[str, Any]:
    """Returns India VIX historical data with 1-year percentile calculation.

    Data source: NSE bhavcopy data ingested by the BUILD-5 ingester (swayam_bhavcopy table).
    Falls back to swayam_config cached VIX snapshot for live value.

    Returns:
        dict with: current, regime, dates, values, percentile, percentile_label,
                   p10, p25, p50, p75, p90, year_low, year_high, history_60d
    Raises:
        HTTPException(503): When bhavcopy data is unavailable (not yet ingested).
    """
    now = time.time()
    cache_ttl = 1800  # 30 min — bhavcopy only updates daily
    if _vix_cache["data"] and (now - _vix_cache["timestamp"]) < cache_ttl:
        return _vix_cache["data"]

    try:
        client = db.client
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        res = (
            client.table("swayam_bhavcopy")
            .select("date, vix_close")
            .gte("date", cutoff)
            .order("date", desc=False)
            .execute()
        )
        rows = res.data or []

        if not rows:
            raise HTTPException(
                status_code=503,
                detail=(
                    "India VIX historical data not available. "
                    "Run the bhavcopy ingester to backfill: "
                    "`python scripts/ingest_bhavcopy.py --days 365`"
                ),
            )

        dates = [r["date"] for r in rows]
        values = [float(r["vix_close"]) for r in rows]
        current_vix = values[-1] if values else 0.0

        # 1-year percentile stats
        sorted_vals = sorted(values)
        n = len(sorted_vals)

        def percentile_val(p: float) -> float:
            idx = (p / 100) * (n - 1)
            lo, hi = int(idx), min(int(idx) + 1, n - 1)
            return round(sorted_vals[lo] + (idx - lo) * (sorted_vals[hi] - sorted_vals[lo]), 2)

        p10 = percentile_val(10)
        p25 = percentile_val(25)
        p50 = percentile_val(50)
        p75 = percentile_val(75)
        p90 = percentile_val(90)

        # Current VIX percentile rank
        below_count = sum(1 for v in values if v < current_vix)
        percentile_rank = round((below_count / n) * 100, 1) if n > 0 else 50.0

        # Regime classification
        if percentile_rank < 25:
            regime = "Low Vol"
        elif percentile_rank < 75:
            regime = "Normal"
        elif percentile_rank < 90:
            regime = "Elevated"
        else:
            regime = "Spike"

        # 60-day window for chart
        history_60d_rows = rows[-60:] if len(rows) >= 60 else rows
        history_60d = {
            "dates": [r["date"] for r in history_60d_rows],
            "values": [float(r["vix_close"]) for r in history_60d_rows],
        }

        result: dict[str, Any] = {
            "current": round(current_vix, 2),
            "regime": regime,
            "percentile": percentile_rank,
            "percentile_label": f"{current_vix:.2f} is in the {percentile_rank:.0f}th percentile of last {len(values)} days",
            "year_low": round(min(values), 2),
            "year_high": round(max(values), 2),
            "p10": p10,
            "p25": p25,
            "p50": p50,
            "p75": p75,
            "p90": p90,
            "history_60d": history_60d,
            "as_of": dates[-1] if dates else None,
        }
        _vix_cache["data"] = result
        _vix_cache["timestamp"] = now
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to load VIX history from database: {e}",
        ) from e
