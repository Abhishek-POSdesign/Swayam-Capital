"""
Live market data endpoints for Swayam Capital.

Interacts with FYERS API v3 to provide live NIFTY index spot quotes and
full option chains with in-memory caching to respect rate limits.

BUILD-9-FIXES-A additions:
  GET /api/market/nifty/candles?timeframe=15m|1h|1d  — for interactive chart tabs
  GET /api/market/vix/history?days=N                 — for VIX percentile band
"""

from datetime import date, datetime, time as _dtime, timedelta, timezone
import time
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from swayam.api.chain_feed import ChainSnapshot, chain_feed
from swayam.api.models_api import OptionChainResponse, StrikeQuote, StrikeRow
from swayam.fyers_client import fyers_client
from swayam.db import db
from swayam.services.expiry import get_expiry_metadata, is_trading_day
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


def fetch_chain_snapshot(symbol: str, strike_count: int, timestamp: Optional[str] = None) -> ChainSnapshot:
    """The chain for one expiry, with the age of the reading attached.

    A browser request never calls FYERS while the feed already holds that
    expiry. It registers interest and reads what the feed last fetched. Only a
    completely cold cache costs one inline call, so the first page load of the
    day is not blank while the feed makes its first pass.

    This replaced a three-second cache that the desk's five-second re-quote
    always outlived, so every leg on every poll became a FYERS call and FYERS
    began refusing. Raises whatever the client raises, but only on that cold
    path; nothing is ever substituted.
    """
    key = chain_feed.register(symbol, strike_count, timestamp)
    snap = chain_feed.snapshot(key)
    if snap.data is not None:
        return snap
    chain_feed.fetch_now(key)
    return chain_feed.snapshot(key)


def fetch_chain_cached(symbol: str, strike_count: int, timestamp: Optional[str] = None) -> dict[str, Any]:
    """The chain itself, for callers that do not need to know its age."""
    return fetch_chain_snapshot(symbol, strike_count, timestamp).data or {}


# The order matters: the screen shows the worst of the sources, so one glance
# is enough and nothing hides behind an average.
_STATE_RANK = {"live": 0, "closing": 1, "delayed": 2, "unavailable": 3}


@router.get("/api/market/data-health")
def get_data_health(request: Request) -> dict[str, Any]:
    """Whether the numbers on screen are live, old, or missing, and why.

    He asked for exactly one thing here: if FYERS stops giving data while he is
    trading, he must know, without having to notice that a number stopped
    moving. This is the single answer the screen reads. It never guesses and it
    never smooths over a failure.
    """
    now_ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    market_open = chain_feed.is_open()

    # ---- the option chain
    watching = chain_feed.wanted_keys()
    chain_snaps = [chain_feed.snapshot(k) for k in watching]
    fresh = [s for s in chain_snaps if s.data is not None]
    if not watching:
        chain_state = "live" if market_open else "closing"
        chain_detail = "No expiry is being watched yet."
        chain_age = None
    elif not fresh:
        chain_state = "unavailable"
        chain_detail = chain_feed.explain() or "The option chain has not been read."
        chain_age = None
    else:
        newest = min(fresh, key=lambda s: s.age_seconds if s.age_seconds is not None else 1e9)
        chain_state = newest.state
        chain_age = newest.as_dict()["age_seconds"]
        chain_detail = (
            f"Option chain read {chain_age:.0f} seconds ago."
            if chain_age is not None
            else "Option chain read."
        )
        if chain_feed.explain():
            chain_state = "delayed" if market_open else "closing"
            chain_detail = chain_feed.explain() or chain_detail

    # ---- the spot tick feed
    feed = getattr(request.app.state, "spot_feed", None)
    if feed is None:
        spot_state = "unavailable"
        spot_detail = "The tick feed is not running in this process."
        spot_status: dict[str, Any] = {}
    else:
        spot_status = feed.status()
        last = spot_status.get("last_tick") or {}
        if not market_open:
            spot_state = "closing"
            spot_detail = "Market is shut. Showing the last price of the session."
        elif spot_status.get("last_error"):
            spot_state = "delayed"
            spot_detail = f"The last spot read failed: {spot_status['last_error']}"
        elif not last:
            spot_state = "unavailable"
            spot_detail = "No tick has arrived yet."
        else:
            spot_state = "live"
            spot_detail = f"Spot ticking, {spot_status.get('frames_sent', 0)} frames sent."

    worst = max([chain_state, spot_state], key=lambda s: _STATE_RANK.get(s, 3))
    headline = {
        "live": "Live prices from FYERS",
        "closing": "Closing prices, market is shut",
        "delayed": "Prices are behind",
        "unavailable": "No prices from FYERS",
    }[worst]

    # What HE should do about it, in his own terms, or nothing when all is well.
    action: Optional[str] = None
    if worst in ("delayed", "unavailable"):
        last_error = chain_feed.last_error or spot_status.get("last_error") or ""
        if "token" in last_error.lower():
            action = (
                "Refresh your FYERS token, then restart the service, because the running "
                "container will not pick up a new token on its own."
            )
        elif chain_feed.backoff_until > time.time():
            action = (
                "Nothing to do. Too many requests went to FYERS and it is waiting before "
                "asking again. Prices should return on their own."
            )
        else:
            action = "Type your own price on any leg to keep working. Nothing is invented while this lasts."

    return {
        "state": worst,
        "headline": headline,
        "detail": f"{chain_detail} {spot_detail}".strip(),
        "action": action,
        "market_open": market_open,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "ist_time": now_ist.strftime("%H:%M"),
        "sources": {
            "chain": {
                "state": chain_state,
                "detail": chain_detail,
                "age_seconds": chain_age,
                "expiries_watched": len(watching),
                "fyers_calls": chain_feed.fetches,
                "fyers_refusals": chain_feed.refusals,
                "backoff_seconds_remaining": round(max(0.0, chain_feed.backoff_until - time.time()), 1),
                "error": chain_feed.last_error,
            },
            "spot": {
                "state": spot_state,
                "detail": spot_detail,
                "frames_sent": spot_status.get("frames_sent"),
                "role": spot_status.get("role"),
                "error": spot_status.get("last_error"),
            },
        },
    }


def resolve_expiry_epoch(base_chain: dict[str, Any], expiry_iso: str) -> Optional[str]:
    """Maps YYYY-MM-DD to FYERS' epoch for that expiry via the chain's expiryData.

    FYERS dates its expiries DD-MM-YYYY. None when the expiry is not listed,
    in which case the caller must not pretend the nearest expiry is the one
    asked for.
    """
    try:
        want = datetime.strptime(expiry_iso, "%Y-%m-%d").strftime("%d-%m-%Y")
    except (TypeError, ValueError):
        return None
    for ed in base_chain.get("expiryData", []) or []:
        if ed.get("date") == want and ed.get("expiry") is not None:
            return str(ed.get("expiry"))
    return None


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


def _opt_float(value: Any) -> Optional[float]:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _opt_int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def parse_chain_rows(rows: list[dict[str, Any]], *, spot: Optional[float], tte_years: Optional[float]) -> list[StrikeRow]:
    """Groups FYERS' per-contract rows by strike and solves IV from each traded price."""
    from swayam.options_math.engine import IVSolveFailed, implied_volatility
    from swayam.options_math.models import OptionType

    by_strike: dict[float, dict[str, StrikeQuote]] = {}
    for r in rows:
        ot = r.get("option_type")
        if ot not in ("CE", "PE"):
            continue
        k = _opt_float(r.get("strike_price", r.get("strike")))
        if not k or k <= 0:
            continue
        lp = _opt_float(r.get("ltp"))
        ltp = lp if lp and lp > 0 else None

        iv: Optional[float] = None
        if ltp and spot and tte_years and tte_years > 0:
            try:
                iv = round(
                    float(implied_volatility(
                        market_price=ltp, spot=spot, strike=k, tte_years=tte_years,
                        option_type=OptionType.CALL if ot == "CE" else OptionType.PUT,
                    )),
                    4,
                )
            except (IVSolveFailed, ValueError, Exception):  # noqa: BLE001 - no trade-able IV, so null
                iv = None

        by_strike.setdefault(k, {})[ot] = StrikeQuote(
            ltp=ltp,
            ltp_change=_opt_float(r.get("ltpch")) if ltp else None,
            ltp_change_pct=_opt_float(r.get("ltpchp")) if ltp else None,
            iv=iv,
            oi=_opt_int(r.get("oi")),
            oi_change=_opt_int(r.get("oich")),
            oi_change_pct=_opt_float(r.get("oichp")),
            volume=_opt_int(r.get("volume")),
            bid=_opt_float(r.get("bid")),
            ask=_opt_float(r.get("ask")),
            symbol=r.get("symbol"),
        )

    return [
        StrikeRow(strike=k, ce=by_strike[k].get("CE", StrikeQuote()), pe=by_strike[k].get("PE", StrikeQuote()))
        for k in sorted(by_strike)
    ]


@router.get("/api/option-chain", response_model=OptionChainResponse)
def get_option_chain(
    expiry: str = Query(..., description="Expiration date in YYYY-MM-DD format"),
    strike_count: int = Query(default=20, ge=4, le=50, description="Strikes around ATM"),
) -> OptionChainResponse:
    """The option chain for the expiry asked for, with everything FYERS sends.

    Until round 2 this accepted `expiry`, used it only as a cache key, and
    called FYERS without a timestamp, so it returned the nearest expiry every
    time whatever was asked. A chain for the wrong expiry is worse than no
    chain: the expiry is resolved to FYERS' epoch first and a date FYERS does
    not list is refused.

    Cached for 5 seconds on the RESOLVED expiry.

    Raises:
        HTTPException(404): the expiry is not one FYERS lists.
        HTTPException(503): FYERS is unavailable.
    """
    from swayam.services.nifty_snapshot import calculate_max_pain, compute_pcr_and_walls

    now = time.time()
    try:
        base_chain = fetch_chain_cached("NSE:NIFTY50-INDEX", strike_count)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to fetch option chain from FYERS: {e}") from e

    epoch = resolve_expiry_epoch(base_chain, expiry)
    if epoch is None:
        listed = [ed.get("date") for ed in base_chain.get("expiryData", []) or []]
        raise HTTPException(
            status_code=404,
            detail=f"FYERS does not list an expiry on {expiry}. Listed (DD-MM-YYYY): {', '.join(str(d) for d in listed[:8])}",
        )

    cache_key = f"{epoch}_{strike_count}"
    if cache_key in _chain_cache:
        entry = _chain_cache[cache_key]
        if (now - entry["timestamp"]) < 5.0:
            return entry["data"]

    try:
        raw_chain = fetch_chain_cached("NSE:NIFTY50-INDEX", strike_count, epoch)
        rows = raw_chain.get("optionsChain", []) or []
        if not rows:
            raise RuntimeError("FYERS returned an empty option chain.")

        # Real spot from the underlying row (option_type ""), else live spot; else fail loudly.
        spot: Optional[float] = None
        for r in rows:
            if not r.get("option_type"):
                spot = _opt_float(r.get("ltp")) or None
                break
        if spot is None:
            spot = float(fyers_client.get_nifty_spot())

        try:
            exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
            days_to_expiry: Optional[int] = max((exp_date - date.today()).days, 0)
            tte_years: Optional[float] = max(days_to_expiry, 0.5) / 365.0
        except ValueError:
            days_to_expiry, tte_years = None, None

        strike_rows = parse_chain_rows(rows, spot=spot, tte_years=tte_years)
        stats = compute_pcr_and_walls(rows)
        atm = min((r.strike for r in strike_rows), key=lambda k: abs(k - spot)) if strike_rows else None

        response = OptionChainResponse(
            underlying="NIFTY",
            expiry=expiry,
            expiry_epoch=epoch,
            spot=spot,
            days_to_expiry=days_to_expiry,
            atm_strike=atm,
            strikes=strike_rows,
            total_call_oi=stats["total_call_oi"] if stats["pcr"] is not None else None,
            total_put_oi=stats["total_put_oi"] if stats["pcr"] is not None else None,
            pcr=stats["pcr"],
            max_pain=calculate_max_pain(rows),
            as_of=datetime.now(timezone.utc).isoformat(),
        )
        _chain_cache[cache_key] = {"data": response, "timestamp": now}
        return response
    except HTTPException:
        raise
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
    quote_error: Optional[str] = None
    freshness: Optional[ChainSnapshot] = None
    try:
        base = fetch_chain_snapshot(symbol, 50)
        base_chain = base.data or {}
        # Map requested expiry (YYYY-MM-DD) -> FYERS epoch via expiryData (dates are DD-MM-YYYY).
        want_epoch = resolve_expiry_epoch(base_chain, expiry)
        # Use the base chain if the requested expiry is the nearest; else the
        # chain for that expiry. Both come from the shared feed, so neither
        # costs a FYERS call while the feed already holds them.
        snap = base
        if want_epoch:
            snap = fetch_chain_snapshot(symbol, 50, want_epoch)
        freshness = snap
        chain = snap.data or {}
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
        # Visible in the logs, not swallowed at debug: a quote that fails is a
        # blank price on his screen, and he should be able to see why.
        quote_error = str(exc)
        logger.warning("Option chain fetch failed for quote (strike=%s expiry=%s): %s", strike, expiry, exc)

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
    # How old the reading actually is, rather than when this response was built.
    # A price the feed read forty seconds ago is not a live price and must not
    # be presented as one.
    chain_state = freshness.state if freshness else "unavailable"
    source = "unavailable"
    if price_available:
        source = {"live": "live", "delayed": "delayed", "closing": "prev_close"}.get(
            chain_state, "live" if market_open else "prev_close"
        )

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
        # When FYERS was actually read, not when this reply was assembled.
        "as_of": (freshness.as_dict()["as_of"] if freshness else None) or datetime.now(timezone.utc).isoformat(),
        "price_age_seconds": freshness.as_dict()["age_seconds"] if freshness else None,
        "freshness": chain_state,
        "note": (
            None if price_available
            else (
                f"The chain could not be read ({quote_error}). No price is invented; the last one you had is kept if you had one."
                if quote_error
                else "No real price found for this strike/expiry — type your own price. (No fabricated prices, ever.)"
            )
        ),
        "error": quote_error or (freshness.error if freshness else None),
    }


@router.get("/api/market/expiries")
def get_expiries() -> dict[str, Any]:
    """Returns the real upcoming NIFTY expiries (Tuesday-migrated, holiday-adjusted) for the
    per-leg expiry dropdown. Sourced from the FYERS contract master with disk-cache + computed
    fallback, so it works off-hours. Each item carries a human label and weekly/monthly flags.

    An expiry is dropped the moment its day is over. This used to keep it, so
    on a weekly expiry evening the desk still offered "08 Sep (0d)", those
    contracts no longer existed, and every price read 0.05, which is what an
    expired option is worth. That is what he reported as losing all the prices
    after the close.
    """
    try:
        meta = get_expiry_metadata()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Expiry metadata unavailable: {e}") from e

    today = date.today()
    now_ist = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    # On expiry day the contracts die at 15:30 IST. Before that they are the
    # live front month and must stay; after it they are gone.
    todays_expiry_is_over = now_ist.time() > _dtime(15, 30)

    items: list[dict[str, Any]] = []
    dropped: list[str] = []
    for iso in meta.get("upcoming_expiries", []):
        try:
            d = date.fromisoformat(iso)
        except ValueError:
            continue
        cal = (d - today).days
        if cal < 0 or (cal == 0 and todays_expiry_is_over):
            dropped.append(iso)
            continue
        items.append(
            {
                "date": iso,
                "calendar_days": cal,
                "label": f"{d.strftime('%d %b')} ({cal}d)",
                "is_weekly": False,
                "is_monthly": iso == meta.get("monthly_expiry"),
            }
        )

    live_dates = {item["date"] for item in items}

    def _still_live(iso: Optional[str]) -> Optional[str]:
        """Never point the desk at an expiry that has just been dropped."""
        return iso if iso in live_dates else (items[0]["date"] if items else None)

    # The flags are set only after the dropping, or the row for the weekly that
    # just expired takes the badge with it and no row carries one at all.
    weekly = _still_live(meta.get("weekly_expiry"))
    monthly = _still_live(meta.get("monthly_expiry"))
    for item in items:
        item["is_weekly"] = item["date"] == weekly
        item["is_monthly"] = item["date"] == monthly

    # The desk assumes he carries a position overnight (he arrives at 2:30 pm
    # for swing and positional trades), so it needs the next trading day to
    # send as the planned exit. Computed here from the NSE holiday file so the
    # browser never guesses at a holiday.
    next_trading_day: Optional[str] = None
    try:
        candidate = today + timedelta(days=1)
        for _ in range(15):
            if is_trading_day(candidate):
                next_trading_day = candidate.isoformat()
                break
            candidate += timedelta(days=1)
    except Exception as e:  # noqa: BLE001 - reported as unavailable, never guessed
        logger.warning("Next trading day could not be computed: %s", e)

    return {
        "expiries": items,
        "weekly_expiry": weekly,
        "monthly_expiry": monthly,
        "today": today.isoformat(),
        "next_trading_day": next_trading_day,
        # Named so the desk can say why the expiry it had selected vanished,
        # rather than silently switching under him.
        "expired_today": dropped,
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
        # At least 20 real rows are guaranteed above, so the last close is
        # real. No zero fallback: a VIX of zero was never a measurement.
        current_vix = values[-1]

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
        # n >= 20 here. A "50th percentile" default was a fabricated regime.
        percentile_rank = round((below_count / n) * 100, 1)

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
