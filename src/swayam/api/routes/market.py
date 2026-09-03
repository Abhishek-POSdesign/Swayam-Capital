"""
Live market data endpoints for Swayam Capital.

Interacts with FYERS API v3 to provide live NIFTY index spot quotes and
full option chains with in-memory caching to respect rate limits.
"""

from datetime import datetime, timezone
import time
from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query
from swayam.api.models_api import OptionChainResponse, StrikeQuote, StrikeRow
from swayam.fyers_client import fyers_client

router = APIRouter()

# In-memory caches
_spot_cache: dict[str, Any] = {"data": None, "timestamp": 0.0}
_chain_cache: dict[str, Any] = {}


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
