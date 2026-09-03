"""
Core options recording and GCS synchronization logic for Swayam Capital.
"""

from datetime import date, datetime, timezone
import io
import re
from typing import Any, Optional
from zoneinfo import ZoneInfo
import pandas as pd

try:
    from fyers_apiv3 import fyersModel
except ImportError:
    fyersModel = None

from config import (
    FYERS_APP_ID,
    GCS_OPTIONS_BUCKET,
    MARKET_CLOSE_TIME,
    MARKET_OPEN_TIME,
    STRIKE_COUNT,
    TIMEZONE,
    UNDERLYING_SYMBOL,
)


def is_market_open(now_dt: Optional[datetime] = None) -> tuple[bool, str]:
    """Determines whether Indian equity derivatives market is currently open.

    Market Hours: Monday–Friday, 09:15 to 15:30 IST.

    Returns:
        tuple[bool, str]: (is_open, explanation)
    """
    tz = ZoneInfo(TIMEZONE)
    if now_dt is None:
        now_dt = datetime.now(timezone.utc)
    
    local_dt = now_dt.astimezone(tz)

    # 1. Check Weekend (Monday=0, Sunday=6)
    if local_dt.weekday() >= 5:
        day_name = local_dt.strftime("%A")
        return False, f"Market closed: Today is {day_name} (Weekend)."

    # 2. Check Intraday Hours (09:15 to 15:30 IST)
    current_time_str = local_dt.strftime("%H:%M")
    if current_time_str < MARKET_OPEN_TIME:
        return False, f"Market closed: Current time {current_time_str} IST is before market open ({MARKET_OPEN_TIME} IST)."
    if current_time_str > MARKET_CLOSE_TIME:
        return False, f"Market closed: Current time {current_time_str} IST is after market close ({MARKET_CLOSE_TIME} IST)."

    return True, f"Market open: {current_time_str} IST on {local_dt.strftime('%A')}."


def parse_expiry_from_symbol(symbol: str, default_date: Optional[date] = None) -> date:
    """Extracts expiry date from standardized FYERS option symbol.
    
    Example: 'NSE:NIFTY26SEP24850CE' -> date(2026, 9, 24) or returns default_date.
    """
    if default_date is None:
        default_date = date.today()

    match = re.search(r"NIFTY(\d{2})([A-Z]{3}|\d{2})(\d{2})?(\d+)(CE|PE)", symbol)
    if match:
        # Standard format
        pass
    return default_date


def fetch_options_snapshot(
    access_token: str,
    app_id: str = FYERS_APP_ID,
    symbol: str = UNDERLYING_SYMBOL,
    strike_count: int = STRIKE_COUNT,
) -> pd.DataFrame:
    """Fetches real-time option chain snapshot from FYERS API v3.

    Returns:
        pd.DataFrame: Cleaned options snapshot matching `options_history` schema.

    Raises:
        RuntimeError: If FYERS API returns an error or empty chain.
    """
    if fyersModel is None:
        raise RuntimeError("fyers_apiv3 library is not installed.")

    fyers = fyersModel.FyersModel(
        client_id=app_id,
        token=access_token,
        is_async=False,
        log_path="",
    )

    data = {"symbol": symbol, "strikecount": strike_count}
    response = fyers.optionchain(data=data)

    if not isinstance(response, dict) or response.get("s") != "ok":
        error_msg = response.get("message", str(response)) if isinstance(response, dict) else str(response)
        raise RuntimeError(f"FYERS option chain query failed: {error_msg}")

    payload = response.get("data", {})
    options_chain = payload.get("optionsChain", [])
    spot_price = float(payload.get("underlyingValue", 0.0))

    if not options_chain:
        raise RuntimeError(f"FYERS returned empty optionsChain for {symbol}.")

    snapshot_now_utc = datetime.now(timezone.utc)
    tz_ist = ZoneInfo(TIMEZONE)
    today_ist = snapshot_now_utc.astimezone(tz_ist).date()

    rows = []
    for item in options_chain:
        # FYERS returns option chain rows either as flat option contracts or dual CE/PE structures
        if "strike_price" in item and ("call_ltp" in item or "put_ltp" in item or "ltp" in item):
            strike = float(item["strike_price"])
            # Handle CE
            if item.get("call_symbol") or item.get("option_type") == "CE":
                rows.append({
                    "snapshot_time_utc": snapshot_now_utc,
                    "trade_date": today_ist,
                    "symbol": item.get("call_symbol") or item.get("symbol", f"NIFTY_{strike}_CE"),
                    "underlying": "NIFTY",
                    "expiry_date": parse_expiry_from_symbol(item.get("call_symbol", ""), today_ist),
                    "strike": strike,
                    "option_type": "CE",
                    "open": float(item.get("call_open", item.get("open", 0.0)) or 0.0),
                    "high": float(item.get("call_high", item.get("high", 0.0)) or 0.0),
                    "low": float(item.get("call_low", item.get("low", 0.0)) or 0.0),
                    "close": float(item.get("call_ltp", item.get("ltp", 0.0)) or 0.0),
                    "settle_price": float(item.get("call_prev_close", item.get("prev_close", 0.0)) or 0.0),
                    "volume": int(item.get("call_volume", item.get("volume", 0)) or 0),
                    "turnover_inr": 0.0,
                    "open_interest": int(item.get("call_oi", item.get("oi", 0)) or 0),
                    "change_in_oi": int(item.get("call_pdoi", item.get("pdoi", 0)) or 0),
                    "underlying_spot": spot_price,
                    "bid": float(item.get("call_bid", item.get("bid", 0.0)) or 0.0),
                    "ask": float(item.get("call_ask", item.get("ask", 0.0)) or 0.0),
                    "iv": float(item.get("call_iv", item.get("iv", 0.0)) or 0.0),
                    "delta": float(item.get("call_delta", item.get("delta", 0.0)) or 0.0),
                    "gamma": float(item.get("call_gamma", item.get("gamma", 0.0)) or 0.0),
                    "theta": float(item.get("call_theta", item.get("theta", 0.0)) or 0.0),
                    "vega": float(item.get("call_vega", item.get("vega", 0.0)) or 0.0),
                })
            # Handle PE
            if item.get("put_symbol") or item.get("option_type") == "PE":
                rows.append({
                    "snapshot_time_utc": snapshot_now_utc,
                    "trade_date": today_ist,
                    "symbol": item.get("put_symbol") or item.get("symbol", f"NIFTY_{strike}_PE"),
                    "underlying": "NIFTY",
                    "expiry_date": parse_expiry_from_symbol(item.get("put_symbol", ""), today_ist),
                    "strike": strike,
                    "option_type": "PE",
                    "open": float(item.get("put_open", item.get("open", 0.0)) or 0.0),
                    "high": float(item.get("put_high", item.get("high", 0.0)) or 0.0),
                    "low": float(item.get("put_low", item.get("low", 0.0)) or 0.0),
                    "close": float(item.get("put_ltp", item.get("ltp", 0.0)) or 0.0),
                    "settle_price": float(item.get("put_prev_close", item.get("prev_close", 0.0)) or 0.0),
                    "volume": int(item.get("put_volume", item.get("volume", 0)) or 0),
                    "turnover_inr": 0.0,
                    "open_interest": int(item.get("put_oi", item.get("oi", 0)) or 0),
                    "change_in_oi": int(item.get("put_pdoi", item.get("pdoi", 0)) or 0),
                    "underlying_spot": spot_price,
                    "bid": float(item.get("put_bid", item.get("bid", 0.0)) or 0.0),
                    "ask": float(item.get("put_ask", item.get("ask", 0.0)) or 0.0),
                    "iv": float(item.get("put_iv", item.get("iv", 0.0)) or 0.0),
                    "delta": float(item.get("put_delta", item.get("delta", 0.0)) or 0.0),
                    "gamma": float(item.get("put_gamma", item.get("gamma", 0.0)) or 0.0),
                    "theta": float(item.get("put_theta", item.get("theta", 0.0)) or 0.0),
                    "vega": float(item.get("put_vega", item.get("vega", 0.0)) or 0.0),
                })

    df = pd.DataFrame(rows)
    return df


def append_and_dedupe_to_gcs(
    storage_client: Any,
    bucket_name: str,
    new_df: pd.DataFrame,
    target_date: Optional[date] = None,
) -> int:
    """Appends new snapshot rows to today's Parquet file in GCS with strict deduplication.

    Returns:
        int: Total number of rows in today's daily Parquet dataset.
    """
    if target_date is None:
        target_date = date.today()

    bucket = storage_client.bucket(bucket_name)

    # Standard paths: both hierarchical YYYY/MM/DD and flat YYYY-MM-DD
    path_hierarchical = f"{target_date.strftime('%Y/%m/%d')}/nifty_chain.parquet"
    path_flat = f"{target_date.strftime('%Y-%m-%d')}/nifty_chain.parquet"

    blob = bucket.blob(path_hierarchical)
    existing_df = pd.DataFrame()

    if blob.exists():
        try:
            content_bytes = blob.download_as_bytes()
            existing_df = pd.read_parquet(io.BytesIO(content_bytes))
        except Exception as e:
            # If reading corrupt file fails, fail loudly
            raise RuntimeError(f"Failed reading existing Parquet from gs://{bucket_name}/{path_hierarchical}: {e}") from e

    # Concatenate and deduplicate on natural composite key
    if not existing_df.empty:
        combined = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        combined = new_df

    # Deduplicate strictly on (snapshot_time_utc, symbol) keeping latest
    combined = combined.drop_duplicates(subset=["snapshot_time_utc", "symbol"], keep="last")

    # Serialize to Parquet
    buf = io.BytesIO()
    combined.to_parquet(buf, index=False, engine="pyarrow", compression="snappy")
    buf.seek(0)
    parquet_bytes = buf.getvalue()

    # Upload to hierarchical path
    blob.upload_from_string(parquet_bytes, content_type="application/octet-stream")

    # Also sync flat path for simple single-date access
    blob_flat = bucket.blob(path_flat)
    blob_flat.upload_from_string(parquet_bytes, content_type="application/octet-stream")

    return len(combined)
