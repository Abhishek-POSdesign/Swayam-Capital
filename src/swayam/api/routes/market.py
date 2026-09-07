"""
Live market data endpoints for Swayam Capital.

Interacts with FYERS API v3 to provide live NIFTY index spot quotes and
full option chains with in-memory caching to respect rate limits.

BUILD-9-FIXES-A additions:
  GET /api/market/nifty/candles?timeframe=15m|1h|1d  — for interactive chart tabs
  GET /api/market/vix/history?days=N                 — for VIX percentile band
"""

from datetime import date, datetime, timedelta, timezone
import time
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query
from swayam.api.models_api import OptionChainResponse, StrikeQuote, StrikeRow
from swayam.fyers_client import fyers_client
from swayam.db import db
from swayam.services.expiry import get_expiry_metadata
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
        raw_chain = fyers_client.get_option_chain(underlying="NSE:NIFTY50-INDEX", strike_count=strike_count)
        rows = raw_chain.get("optionsChain", []) or []

        # Real spot from the underlying row (option_type ""), else live spot; else fail loudly.
        spot: Optional[float] = None
        for r in rows:
            if not r.get("option_type"):
                spot = float(r.get("ltp") or 0) or None
                break
        if spot is None:
            spot = float(fyers_client.get_nifty_spot())
        if not rows:
            raise RuntimeError("FYERS returned an empty option chain.")

        # Group CE/PE by strike. IV is not provided by FYERS and not solved here (this endpoint
        # is not the builder's per-leg path); it is left null rather than faked.
        by_strike: dict[float, dict[str, StrikeQuote]] = {}
        for r in rows:
            ot = r.get("option_type")
            if ot not in ("CE", "PE"):
                continue
            k = float(r.get("strike_price", r.get("strike", 0)) or 0)
            lp = float(r.get("ltp", 0) or 0)
            by_strike.setdefault(k, {})[ot] = StrikeQuote(
                ltp=lp if lp > 0 else None,
                iv=None,
                oi=int(r.get("oi", 0) or 0),
            )

        strike_rows: list[StrikeRow] = []
        for k in sorted(by_strike):
            strike_rows.append(
                StrikeRow(
                    strike=k,
                    ce=by_strike[k].get("CE", StrikeQuote()),
                    pe=by_strike[k].get("PE", StrikeQuote()),
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


@router.get("/api/market/option/quote")
def get_option_quote(
    strike: float = Query(..., description="Strike price (e.g. 24850)"),
    expiry: str = Query(..., description="Expiration date (YYYY-MM-DD)"),
    type: str = Query(..., description="Option type: CE or PE"),
    symbol: str = Query(default="NSE:NIFTY50-INDEX", description="Option underlying symbol"),
) -> dict[str, Any]:
    """Returns a leg quote for the Strategy Builder.

    No-fake-numbers law: LTP/IV/Greeks are returned ONLY when a real market price is found
    in the live FYERS chain. IV is implied from that real LTP; Greeks are computed from it.
    If no real price is available (market closed, data gap, or a non-nearest expiry we can't
    yet resolve), `available` is False and every price field is null — the UI must then let
    the user type a price, from which IV and Delta are computed elsewhere. We never invent an
    LTP, IV, or Delta here.

    NOTE (live verification pending, Monday 2026-09-08): the live-chain parse below targets
    FYERS' `optionsChain` shape and is confirmed offline to fail *safe* (-> available False).
    Real-tick behaviour and non-nearest-expiry epoch resolution get verified during market hours.
    """
    opt_type = type.upper()
    if opt_type not in ("CE", "PE"):
        raise HTTPException(status_code=400, detail="Invalid option type. Must be CE or PE.")

    from swayam.options_math.engine import greeks as bs_greeks, implied_volatility, IVSolveFailed
    from swayam.options_math.models import OptionType

    # Real spot — no fake fallback. None if unavailable.
    spot: Optional[float] = None
    try:
        spot = float(fyers_client.get_nifty_spot())
    except Exception:
        spot = None

    # Days to expiry (real calendar math; None if the date is unparseable).
    days_to_expiry: Optional[int] = None
    tte_years: Optional[float] = None
    try:
        exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
        days_to_expiry = max((exp_date - date.today()).days, 0)
        tte_years = max(days_to_expiry, 0.5) / 365.0
    except Exception:
        days_to_expiry = None
        tte_years = None

    # --- Resolve the REAL price for the REQUESTED expiry (not just the nearest). ---
    # FYERS optionchain returns expiryData (date -> epoch); we pass that epoch as `timestamp`
    # to fetch the exact expiry's chain. Off-hours this returns the last-traded (previous close)
    # price, which is REAL market data — we never fabricate an LTP.
    from datetime import timedelta as _timedelta, time as _dtime

    # Market status in IST (NIFTY F&O trades Mon-Fri 09:15-15:30 IST).
    now_ist = datetime.now(timezone.utc) + _timedelta(hours=5, minutes=30)
    market_open = now_ist.weekday() < 5 and _dtime(9, 15) <= now_ist.time() <= _dtime(15, 30)

    ltp: Optional[float] = None
    oi: Optional[int] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    try:
        base_chain = fyers_client.get_option_chain(underlying=symbol, strike_count=50)
        # Map requested expiry (YYYY-MM-DD) -> FYERS epoch via expiryData (dates are DD-MM-YYYY).
        want_ddmmyyyy = None
        try:
            want_ddmmyyyy = datetime.strptime(expiry, "%Y-%m-%d").strftime("%d-%m-%Y")
        except Exception:
            want_ddmmyyyy = None
        want_epoch = None
        for ed in base_chain.get("expiryData", []) or []:
            if want_ddmmyyyy and ed.get("date") == want_ddmmyyyy:
                want_epoch = str(ed.get("expiry"))
                break
        # Use the base chain if the requested expiry is the nearest; else fetch that expiry by epoch.
        chain = base_chain
        if want_epoch:
            chain = fyers_client.get_option_chain(
                underlying=symbol, strike_count=50, timestamp=want_epoch
            )
        for row in chain.get("optionsChain", []) or []:
            if row.get("option_type") != opt_type:
                continue
            row_strike = float(row.get("strike_price", row.get("strike", 0)) or 0)
            if abs(row_strike - strike) < 0.01:
                cand = float(row.get("ltp", 0) or 0)
                if cand > 0:
                    ltp = cand
                    oi = int(row.get("oi", 0) or 0)
                    bid = row.get("bid")
                    ask = row.get("ask")
                break
    except Exception as exc:
        logger.debug("Option chain fetch failed for quote (strike=%s expiry=%s): %s", strike, expiry, exc)

    # Real IV implied from the real LTP; Greeks computed from that IV. Keep the real price even
    # if the IV solve fails (show the price, just omit Greeks) — never hide a real number.
    iv_val: Optional[float] = None
    delta = gamma = theta = vega = None
    can_greek = bool(ltp and ltp > 0 and spot and tte_years and tte_years > 0)
    if can_greek:
        model_type = OptionType.CALL if opt_type == "CE" else OptionType.PUT
        try:
            iv_val = implied_volatility(
                market_price=ltp, spot=spot, strike=strike, tte_years=tte_years, option_type=model_type
            )
            g = bs_greeks(spot=spot, strike=strike, tte_years=tte_years, iv=iv_val, option_type=model_type)
            delta = round(g.get("delta", 0.0), 3)
            gamma = round(g.get("gamma", 0.0), 5)
            theta = round(g.get("theta", 0.0), 2)
            vega = round(g.get("vega", 0.0), 2)
        except (IVSolveFailed, Exception):
            iv_val = None

    price_available = bool(ltp and ltp > 0)
    source = "unavailable"
    if price_available:
        source = "live" if market_open else "prev_close"

    return {
        "symbol": symbol,
        "strike": strike,
        "expiry": expiry,
        "option_type": opt_type,
        "available": price_available,
        "source": source,
        "ltp": round(float(ltp), 2) if price_available else None,
        "iv": round(float(iv_val), 4) if iv_val else None,
        "oi": oi if price_available else None,
        "bid": bid if price_available else None,
        "ask": ask if price_available else None,
        "delta": delta,
        "gamma": gamma,
        "theta": theta,
        "vega": vega,
        "spot": round(float(spot), 2) if spot else None,
        "market_open": market_open,
        "days_to_expiry": days_to_expiry,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "note": (
            None if price_available
            else "No real price found for this strike/expiry — type your own price. (No fabricated prices, ever.)"
        ),
    }


@router.get("/api/market/expiries")
def get_expiries() -> dict[str, Any]:
    """Returns the real upcoming NIFTY expiries (Tuesday-migrated, holiday-adjusted) for the
    per-leg expiry dropdown. Sourced from the FYERS contract master with disk-cache + computed
    fallback, so it works off-hours. Each item carries a human label and weekly/monthly flags.
    """
    try:
        meta = get_expiry_metadata()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Expiry metadata unavailable: {e}") from e

    today = date.today()
    items: list[dict[str, Any]] = []
    for iso in meta.get("upcoming_expiries", []):
        try:
            d = date.fromisoformat(iso)
        except ValueError:
            continue
        cal = (d - today).days
        items.append(
            {
                "date": iso,
                "calendar_days": cal,
                "label": f"{d.strftime('%d %b')} ({cal}d)",
                "is_weekly": iso == meta.get("weekly_expiry"),
                "is_monthly": iso == meta.get("monthly_expiry"),
            }
        )

    return {
        "expiries": items,
        "weekly_expiry": meta.get("weekly_expiry"),
        "monthly_expiry": meta.get("monthly_expiry"),
    }


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

    dates: list[str] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    is_fallback = False

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
            raise RuntimeError(f"FYERS returned no candle data for timeframe={tf}")

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

    except Exception as e:
        logger.warning("FYERS historical candles failed (%s), attempting database fallback: %s", tf, e)
        dates, opens, highs, lows, closes, is_fallback = _get_nifty_candle_fallback(tf, days_back)
        if not closes:
            raise HTTPException(
                status_code=503,
                detail=f"NIFTY candle data unavailable from both FYERS ({e}) and database fallback.",
            ) from e

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
        "fallback": is_fallback,
    }
    _candle_cache[tf] = {"data": result, "timestamp": now}
    return result


def _get_nifty_candle_fallback(
    tf: str, days_back: int
) -> tuple[list[str], list[float], list[float], list[float], list[float], bool]:
    """Fallback to Supabase swayam_nifty_daily_bars when FYERS is unavailable."""
    try:
        client = db.client
        res = (
            client.table("swayam_nifty_daily_bars")
            .select("trade_date, open, high, low, close")
            .order("trade_date", desc=False)
            .limit(max(days_back, 45))
            .execute()
        )
        rows = res.data or []

        if not rows:
            return [], [], [], [], [], False

        if tf == "1d":
            d = [r.get("trade_date") or r.get("date") for r in rows]
            o = [round(float(r["open"]), 2) for r in rows]
            h = [round(float(r["high"]), 2) for r in rows]
            l = [round(float(r["low"]), 2) for r in rows]
            c = [round(float(r["close"]), 2) for r in rows]
            return d, o, h, l, c, True

        # No-fake law: never synthesize intraday candles from daily OHLC. If FYERS has no
        # real intraday data, report unavailable so the UI shows nothing rather than fiction.
        return [], [], [], [], [], False

        # (Legacy synthesis below is intentionally unreachable, kept only for reference.)
        # For intraday (1h, 15m), synthesize realistic bars from recent daily bars
        recent_rows = rows[-5:] if len(rows) >= 5 else rows
        synth_dates: list[str] = []
        synth_opens: list[float] = []
        synth_highs: list[float] = []
        synth_lows: list[float] = []
        synth_closes: list[float] = []

        if tf == "1h":
            hours = ["09:15", "10:15", "11:15", "12:15", "13:15", "14:15"]
            for r in recent_rows:
                day_d = r.get("trade_date") or r.get("date")
                day_o = round(float(r["open"]), 2)
                day_h = round(float(r["high"]), 2)
                day_l = round(float(r["low"]), 2)
                day_c = round(float(r["close"]), 2)

                prev_close = day_o
                for i, hr in enumerate(hours):
                    ts = f"{day_d}T{hr}:00"
                    bar_open = prev_close
                    if i == 0:
                        bar_close = round(day_o + (day_c - day_o) * 0.2, 2)
                        bar_high = max(bar_open, bar_close, round(day_o + (day_h - day_o) * 0.5, 2))
                        bar_low = min(bar_open, bar_close, round(day_o - (day_o - day_l) * 0.3, 2))
                    elif i == 1:
                        bar_high = day_h
                        bar_close = round((day_h + day_l) / 2, 2)
                        bar_low = min(bar_open, bar_close)
                    elif i == 2:
                        bar_low = day_l
                        bar_close = round(day_l + (day_h - day_l) * 0.4, 2)
                        bar_high = max(bar_open, bar_close)
                    elif i == 5:
                        bar_close = day_c
                        bar_high = max(bar_open, bar_close)
                        bar_low = min(bar_open, bar_close)
                    else:
                        bar_close = round(bar_open + (day_c - bar_open) * 0.3, 2)
                        bar_high = max(bar_open, bar_close) + 10.0
                        bar_low = min(bar_open, bar_close) - 10.0

                    synth_dates.append(ts)
                    synth_opens.append(bar_open)
                    synth_highs.append(bar_high)
                    synth_lows.append(bar_low)
                    synth_closes.append(bar_close)
                    prev_close = bar_close

            return synth_dates, synth_opens, synth_highs, synth_lows, synth_closes, True

        else:  # "15m"
            import math
            ultra_recent = recent_rows[-5:] if len(recent_rows) >= 5 else recent_rows
            times_15m = [
                f"{h:02d}:{m:02d}"
                for h in range(9, 16)
                for m in (0, 15, 30, 45)
                if (h > 9 or m >= 15) and (h < 15 or m <= 30)
            ]
            total_steps = len(times_15m)
            for r in ultra_recent:
                day_d = r.get("trade_date") or r.get("date")
                day_o = round(float(r["open"]), 2)
                day_h = round(float(r["high"]), 2)
                day_l = round(float(r["low"]), 2)
                day_c = round(float(r["close"]), 2)
                day_range = max(day_h - day_l, 40.0)

                prev_c = day_o
                for idx, t in enumerate(times_15m):
                    ts = f"{day_d}T{t}:00"
                    b_open = prev_c
                    progress = (idx + 1) / total_steps
                    base = day_o + (day_c - day_o) * progress
                    # Natural market wave
                    wave = (day_range * 0.22) * math.sin(idx * 0.55)
                    b_close = round(max(day_l, min(day_h, base + wave)), 2)
                    if idx == total_steps - 1:
                        b_close = day_c

                    # Realistic high and low wicks
                    wick_h = round(max(b_open, b_close) + abs(math.cos(idx * 0.7)) * (day_range * 0.18) + 6.0, 2)
                    wick_l = round(min(b_open, b_close) - abs(math.sin(idx * 0.6)) * (day_range * 0.18) - 6.0, 2)
                    b_high = round(min(day_h, max(b_open, b_close, wick_h)), 2)
                    b_low = round(max(day_l, min(b_open, b_close, wick_l)), 2)

                    synth_dates.append(ts)
                    synth_opens.append(b_open)
                    synth_highs.append(b_high)
                    synth_lows.append(b_low)
                    synth_closes.append(b_close)
                    prev_c = b_close

            return synth_dates, synth_opens, synth_highs, synth_lows, synth_closes, True

    except Exception as exc:
        logger.error("Failed to load NIFTY candle fallback: %s", exc)
        return [], [], [], [], [], False


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

        if not rows or len(rows) < 20:
            # No-fake-numbers law: never synthesize a VIX series. If the real bhavcopy history
            # isn't ingested yet, fail loudly so the UI shows an honest "unavailable" instead of
            # a fabricated curve dressed up as live data.
            logger.warning(
                "VIX history in database has %d rows (< 20) — returning 503, not a synthetic series.",
                len(rows) if rows else 0,
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    f"VIX history unavailable: only {len(rows) if rows else 0} real bhavcopy rows "
                    "(need >= 20). Ingest NSE bhavcopy before the VIX card can show real data."
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
