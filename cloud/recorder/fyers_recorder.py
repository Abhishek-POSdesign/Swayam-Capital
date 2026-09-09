"""Core options recording and GCS synchronization logic for Swayam Capital.

What this records, and what it refuses to record
-----------------------------------------------
Every minute of the trading day this asks FYERS for the NIFTY option chain and
appends a snapshot to today's Parquet file. Its first real day, 2026-09-09,
came back with twelve columns that were zero in all 10,332 rows and a
thirteenth, `expiry_date`, that was wrong in all of them: it said every
contract expired on the day it was recorded, while the contract's own name said
otherwise. A wrong date is worse than a zero, because a zero announces itself.

Both faults had the same cause. This module was written against a shape the
FYERS v3 option chain does not return: `call_ltp`, `put_oi`, `call_iv` and
friends, with a fallback to the flat keys that do exist. The fallback carried
the price, the volume and the open interest, and everything with no fallback
silently became `0.0`. `parse_expiry_from_symbol` was an empty shell that
returned today's date whatever it was given.

What FYERS actually sends, verified against the live API on 2026-09-09 night:

    {"ask": 60.55, "bid": 60.05, "fyToken": "101126091547290", "ltp": 60,
     "ltpch": 38, "ltpchp": 172.73, "oi": 4132375, "oich": 1337635,
     "oichp": 47.86, "option_type": "PE", "prev_oi": 2794740,
     "strike_price": 23300, "symbol": "NSE:NIFTY2691523300PE",
     "volume": 83908175}

plus one row with `option_type` empty and `strike_price` -1, whose `ltp` is the
NIFTY level itself. That row is where the underlying spot comes from; there is
no `underlyingValue` field anywhere in the response, which is why the spot was
zero every minute.

So: price, bid, ask, volume, open interest, change in open interest and the
underlying spot are all real, straight from FYERS. Implied volatility and the
four Greeks are computed from the traded price with `bs_math`. And open, high,
low, settlement price and turnover are written as NULL, because the option
chain does not carry them and inventing them is not an option. They are exactly
the columns the free NSE end-of-day file does carry, which is where they are
meant to come from later.

Two expiries, because he trades calendars
-----------------------------------------
Ten of his twenty-one profitable swing trades were calendar spreads. A calendar
cannot be valued, let alone backtested, from one expiry. So each snapshot
records the nearest expiry and the nearest monthly expiry after it. The far
fetch is fail-safe: if it fails, the near expiry is still written and the
failure is logged, because half a snapshot beats none.
"""

from __future__ import annotations

from datetime import date, datetime, time as dtime, timezone
import io
import json
import logging
from pathlib import Path
import re
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd

try:
    from fyers_apiv3 import fyersModel
except ImportError:
    fyersModel = None

import bs_math
from config import (
    FYERS_APP_ID,
    MARKET_CLOSE_TIME,
    MARKET_OPEN_TIME,
    RISK_FREE_RATE,
    STRIKE_COUNT,
    TIMEZONE,
    UNDERLYING_SYMBOL,
)

logger = logging.getLogger("swayam-recorder")

IST = ZoneInfo(TIMEZONE)
HOLIDAYS_FILE = Path(__file__).resolve().parent / "nse_holidays.json"

# The exchange closes at 15:30 IST, so that is the moment an option expires.
EXPIRY_CLOSE_IST = dtime(15, 30)
SECONDS_IN_YEAR = 365.0 * 24.0 * 60.0 * 60.0

# The FYERS weekly symbol encodes the month as a single character: 1 to 9 for
# January to September, then O, N, D. October cannot be "10" because the day
# follows immediately.
_WEEKLY_MONTH_CODES = {
    "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6,
    "7": 7, "8": 8, "9": 9, "O": 10, "N": 11, "D": 12,
}
_WEEKLY_SYMBOL = re.compile(r"^(?:NSE:)?NIFTY(\d{2})([1-9OND])(\d{2})(\d{3,6})(CE|PE)$")
_MONTHLY_SYMBOL = re.compile(
    r"^(?:NSE:)?NIFTY(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{3,6})(CE|PE)$"
)

# The column order of the Parquet file. `prev_oi` and `tte_years` are new: the
# first lets change-in-open-interest be re-derived and checked rather than
# trusted, the second makes every Greek in the row reproducible without having
# to guess which day-count convention produced it.
COLUMNS = [
    "snapshot_time_utc", "trade_date", "symbol", "underlying", "expiry_date",
    "strike", "option_type", "open", "high", "low", "close", "settle_price",
    "volume", "turnover_inr", "open_interest", "change_in_oi", "prev_oi",
    "underlying_spot", "bid", "ask", "tte_years", "iv", "delta", "gamma",
    "theta", "vega",
]
_NULLABLE_INT_COLUMNS = ["volume", "open_interest", "change_in_oi", "prev_oi"]
# Forced to float even when every value is missing. A column of nothing but
# None lands in Parquet as the `null` type, which has no width and no meaning,
# and the day one real value appears the file's schema changes underneath
# whatever is reading it.
_FLOAT_COLUMNS = [
    "open", "high", "low", "close", "settle_price", "turnover_inr",
    "underlying_spot", "bid", "ask", "strike", "tte_years",
    "iv", "delta", "gamma", "theta", "vega",
]


def load_nse_holidays() -> dict[int, set[date]]:
    """The NSE trading holidays, by year, from the file shipped beside this one.

    A copy of the repository's `data/nse_holidays_2026.json`, because a Cloud
    Function is deployed from this folder alone and cannot see the repository.
    `tests/cloud/test_recorder_market_gate.py` fails if the two ever drift apart.
    """
    try:
        raw = json.loads(HOLIDAYS_FILE.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 - a missing calendar must not stop recording
        logger.warning("Could not read the NSE holiday calendar at %s: %s", HOLIDAYS_FILE, e)
        return {}
    by_year: dict[int, set[date]] = {}
    for year_str, entries in raw.items():
        try:
            year = int(year_str)
        except (TypeError, ValueError):
            continue
        days: set[date] = set()
        for entry in entries or []:
            try:
                days.add(datetime.strptime(entry["date"], "%Y-%m-%d").date())
            except (KeyError, TypeError, ValueError):
                continue
        by_year[year] = days
    return by_year


def is_market_open(now_dt: Optional[datetime] = None) -> tuple[bool, str]:
    """Whether NIFTY options are trading right now: weekday, hours AND holiday.

    The holiday check is new. Without it the recorder ran every minute of a
    closed exchange, FYERS returned the previous session's frozen prices, and it
    wrote a full day of rows that are indistinguishable from a real session
    until you notice nothing moved. A backtest reading that file would take
    trades on a day the market was shut.

    Fails OPEN, deliberately: if the calendar file is missing or does not cover
    this year, recording continues and a warning is logged. Losing a real
    trading day to a stale calendar would be the worse mistake, and it would be
    silent.
    """
    if now_dt is None:
        now_dt = datetime.now(timezone.utc)
    local_dt = now_dt.astimezone(IST)

    if local_dt.weekday() >= 5:
        return False, f"Market closed: Today is {local_dt.strftime('%A')} (Weekend)."

    holidays = load_nse_holidays()
    year_holidays = holidays.get(local_dt.year)
    if year_holidays is None:
        logger.warning(
            "The NSE holiday calendar does not cover %s. Recording anyway; "
            "update cloud/recorder/nse_holidays.json.", local_dt.year
        )
    elif local_dt.date() in year_holidays:
        return False, f"Market closed: {local_dt.date().isoformat()} is an NSE trading holiday."

    current_time_str = local_dt.strftime("%H:%M")
    if current_time_str < MARKET_OPEN_TIME:
        return False, (
            f"Market closed: Current time {current_time_str} IST is before market open "
            f"({MARKET_OPEN_TIME} IST)."
        )
    if current_time_str > MARKET_CLOSE_TIME:
        return False, (
            f"Market closed: Current time {current_time_str} IST is after market close "
            f"({MARKET_CLOSE_TIME} IST)."
        )

    return True, f"Market open: {current_time_str} IST on {local_dt.strftime('%A')}."


def parse_expiry_from_symbol(symbol: str) -> Optional[date]:
    """The expiry encoded in a FYERS option symbol, or None when it is not there.

    `NSE:NIFTY2691523300PE` is the weekly expiring on 15 September 2026: two
    digits of year, one character of month, two digits of day, the strike, the
    option type.

    A MONTHLY symbol such as `NSE:NIFTY26SEP24000CE` carries only the year and
    the month. The day is the last Tuesday of that month, except when that
    Tuesday is a holiday, so it cannot be read off the symbol. This returns None
    for those rather than computing a date that would be wrong a few times a
    year. The authority for the expiry is the date FYERS listed in `expiryData`
    for the chain that was requested; this function exists to CHECK that, not to
    replace it.

    The previous version of this function was an empty shell that returned
    today's date for every symbol it was given, which is how every row of
    2026-09-09 came to claim it expired that afternoon.
    """
    if not symbol:
        return None
    candidate = symbol.strip().upper()

    weekly = _WEEKLY_SYMBOL.match(candidate)
    if weekly:
        year = 2000 + int(weekly.group(1))
        month = _WEEKLY_MONTH_CODES[weekly.group(2)]
        day = int(weekly.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            return None

    if _MONTHLY_SYMBOL.match(candidate):
        return None  # a known shape, but it carries no day
    logger.debug("Symbol %s matches no known NIFTY option shape.", symbol)
    return None


def _parse_expiry_data(payload: dict[str, Any]) -> list[tuple[date, str, str]]:
    """FYERS' `expiryData` as (date, epoch string, 'W' or 'M'), soonest first."""
    parsed: list[tuple[date, str, str]] = []
    for entry in payload.get("expiryData") or []:
        raw_date = entry.get("date")
        epoch = entry.get("expiry")
        if not raw_date or epoch is None:
            continue
        try:
            expiry = datetime.strptime(str(raw_date), "%d-%m-%Y").date()
        except (TypeError, ValueError):
            continue
        parsed.append((expiry, str(epoch), str(entry.get("expiry_flag") or "")))
    parsed.sort(key=lambda row: row[0])
    return parsed


def select_expiries(payload: dict[str, Any]) -> list[tuple[date, Optional[str]]]:
    """The near expiry, and the nearest monthly expiry after it.

    The near one is where his calendars earn theta and where nearly everything
    else he trades sits. The far monthly is the hedge leg of a calendar and the
    reason its margin benefit exists. Recording only the near expiry would leave
    ten of his twenty-one historical trades permanently un-backtestable.

    The near expiry is returned with `None` for the epoch, because the chain for
    it comes back from the call that has already been made.
    """
    listed = _parse_expiry_data(payload)
    if not listed:
        return []
    near_date = listed[0][0]
    chosen: list[tuple[date, Optional[str]]] = [(near_date, None)]

    for expiry, epoch, flag in listed[1:]:
        if flag.upper() == "M" and expiry > near_date:
            chosen.append((expiry, epoch))
            break
    return chosen


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _spot_from_chain(rows: list[dict[str, Any]]) -> Optional[float]:
    """The NIFTY level, from the underlying row FYERS puts in the chain.

    That row has an empty `option_type` and a strike of -1. There is no
    `underlyingValue` key in the response; reading for one is what wrote a zero
    spot into every row of the first recorded day.
    """
    for row in rows:
        if not row.get("option_type"):
            value = _as_float(row.get("ltp"))
            if value is not None and value > 0:
                return value
    return None


def _tte_years(snapshot_utc: datetime, expiry: date) -> Optional[float]:
    """Years from this snapshot to the 15:30 IST close on the expiry day.

    Calendar days would do for a screen. They will not do for an archive that a
    backtest reads: on expiry Tuesday the difference between "one day" and
    "ninety minutes" is the difference between a theta figure that is roughly
    right and one that is nonsense, and expiry day is exactly when his calendars
    are being squared off.
    """
    expiry_close = datetime.combine(expiry, EXPIRY_CLOSE_IST, tzinfo=IST)
    seconds = (expiry_close - snapshot_utc).total_seconds()
    if seconds <= 0:
        return None
    return seconds / SECONDS_IN_YEAR


def build_rows(
    chain_rows: list[dict[str, Any]],
    *,
    expiry: date,
    spot: Optional[float],
    snapshot_utc: datetime,
    trade_date: date,
    rate: float = RISK_FREE_RATE,
) -> list[dict[str, Any]]:
    """Turns one expiry's FYERS rows into snapshot records.

    Anything FYERS does not send is None here and NULL in the Parquet file.
    Never 0.0: a zero open interest and an unknown open interest are different
    facts and the archive has to be able to tell them apart.
    """
    tte = _tte_years(snapshot_utc, expiry)
    records: list[dict[str, Any]] = []

    for row in chain_rows:
        option_type = (row.get("option_type") or "").strip().upper()
        if option_type not in ("CE", "PE"):
            continue  # the underlying row; its price is the spot, handled above
        strike = _as_float(row.get("strike_price"))
        if strike is None or strike <= 0:
            continue

        symbol = row.get("symbol") or ""
        symbol_expiry = parse_expiry_from_symbol(symbol)
        if symbol_expiry is not None and symbol_expiry != expiry:
            # The contract's own name disagrees with the expiry FYERS listed for
            # this chain. Something is wrong upstream; skip the row rather than
            # archive a contract filed under the wrong expiry.
            logger.warning(
                "Skipping %s: its symbol says it expires %s but the chain was requested for %s.",
                symbol, symbol_expiry, expiry,
            )
            continue

        close = _as_float(row.get("ltp"))
        if close is not None and close <= 0:
            close = None

        iv: Optional[float] = None
        delta = gamma = theta = vega = None
        if close is not None and spot is not None and tte is not None:
            iv = bs_math.implied_volatility(
                market_price=close, option_type=option_type, spot=spot,
                strike=strike, tte_years=tte, rate=rate,
            )
            if iv is not None:
                sensitivities = bs_math.greeks(
                    option_type=option_type, spot=spot, strike=strike,
                    tte_years=tte, rate=rate, iv=iv,
                )
                if sensitivities is not None:
                    delta = sensitivities["delta"]
                    gamma = sensitivities["gamma"]
                    theta = sensitivities["theta"]
                    vega = sensitivities["vega"]

        records.append({
            "snapshot_time_utc": snapshot_utc,
            "trade_date": trade_date,
            "symbol": symbol,
            "underlying": "NIFTY",
            "expiry_date": expiry,
            "strike": strike,
            "option_type": option_type,
            # FYERS' option chain carries none of these five. The NSE end-of-day
            # file does, and it is the intended source for them.
            "open": None,
            "high": None,
            "low": None,
            "close": close,
            "settle_price": None,
            "volume": _as_int(row.get("volume")),
            "turnover_inr": None,
            "open_interest": _as_int(row.get("oi")),
            "change_in_oi": _as_int(row.get("oich")),
            "prev_oi": _as_int(row.get("prev_oi")),
            "underlying_spot": spot,
            "bid": _as_float(row.get("bid")),
            "ask": _as_float(row.get("ask")),
            "tte_years": tte,
            "iv": iv,
            "delta": delta,
            "gamma": gamma,
            "theta": theta,
            "vega": vega,
        })
    return records


def to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    """The snapshot as a DataFrame with a stable column order and nullable ints.

    Nullable integers matter: a plain int64 column cannot hold "unknown", so an
    absent open interest would have to become a float, and somewhere downstream
    a float NaN becomes a zero again. `Int64` keeps "unknown" intact all the way
    into the Parquet file.
    """
    df = pd.DataFrame(records, columns=COLUMNS)
    for column in _NULLABLE_INT_COLUMNS:
        df[column] = df[column].astype("Int64")
    for column in _FLOAT_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce").astype("float64")
    return df


def fetch_options_snapshot(
    access_token: str,
    app_id: str = FYERS_APP_ID,
    symbol: str = UNDERLYING_SYMBOL,
    strike_count: int = STRIKE_COUNT,
    client: Any = None,
) -> pd.DataFrame:
    """One snapshot of the NIFTY chain: the near expiry and the nearest monthly.

    Raises:
        RuntimeError: if FYERS refuses, or returns an empty chain, or the
            response contains no NIFTY level to value anything against.
    """
    if client is None:
        if fyersModel is None:
            raise RuntimeError("fyers_apiv3 library is not installed.")
        client = fyersModel.FyersModel(
            client_id=app_id, token=access_token, is_async=False, log_path=""
        )

    response = client.optionchain(data={"symbol": symbol, "strikecount": strike_count})
    if not isinstance(response, dict) or response.get("s") != "ok":
        message = (
            response.get("message", str(response)) if isinstance(response, dict) else str(response)
        )
        raise RuntimeError(f"FYERS option chain query failed: {message}")

    payload = response.get("data", {}) or {}
    near_rows = payload.get("optionsChain") or []
    if not near_rows:
        raise RuntimeError(f"FYERS returned empty optionsChain for {symbol}.")

    spot = _spot_from_chain(near_rows)
    if spot is None:
        # Without the NIFTY level nothing can be valued. Refusing here is
        # deliberate: recording a chain with no spot is what produced a whole
        # day of rows with no implied volatility and no Greeks.
        raise RuntimeError(
            "FYERS returned an option chain with no underlying row, so there is no NIFTY "
            "level to value it against. Nothing recorded for this minute."
        )

    snapshot_utc = datetime.now(timezone.utc)
    trade_date = snapshot_utc.astimezone(IST).date()

    expiries = select_expiries(payload)
    if not expiries:
        raise RuntimeError("FYERS returned no expiryData, so no expiry could be established.")

    records: list[dict[str, Any]] = []
    for expiry, epoch in expiries:
        rows = near_rows
        if epoch is not None:
            try:
                far = client.optionchain(
                    data={"symbol": symbol, "strikecount": strike_count, "timestamp": epoch}
                )
                if not isinstance(far, dict) or far.get("s") != "ok":
                    raise RuntimeError(
                        far.get("message", str(far)) if isinstance(far, dict) else str(far)
                    )
                rows = (far.get("data", {}) or {}).get("optionsChain") or []
                if not rows:
                    raise RuntimeError("empty optionsChain")
            except Exception as e:  # noqa: BLE001 - the near expiry must still be written
                logger.warning(
                    "Could not fetch the far expiry %s (%s). The near expiry is still recorded.",
                    expiry, e,
                )
                continue
        records.extend(
            build_rows(
                rows, expiry=expiry, spot=spot,
                snapshot_utc=snapshot_utc, trade_date=trade_date,
            )
        )

    return to_dataframe(records)


def append_and_dedupe_to_gcs(
    storage_client: Any,
    bucket_name: str,
    new_df: pd.DataFrame,
    target_date: Optional[date] = None,
) -> int:
    """Appends this snapshot to today's Parquet file in GCS, deduplicated.

    `target_date` defaults to the date in INDIA, not the date wherever this
    container happens to run. The two agree during market hours today, and
    relying on that is the kind of assumption that breaks a year later.

    Returns:
        int: Total number of rows in today's daily Parquet dataset.
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).astimezone(IST).date()

    bucket = storage_client.bucket(bucket_name)

    path_hierarchical = f"{target_date.strftime('%Y/%m/%d')}/nifty_chain.parquet"
    path_flat = f"{target_date.strftime('%Y-%m-%d')}/nifty_chain.parquet"

    blob = bucket.blob(path_hierarchical)
    existing_df = pd.DataFrame()

    if blob.exists():
        try:
            content_bytes = blob.download_as_bytes()
            existing_df = pd.read_parquet(io.BytesIO(content_bytes))
        except Exception as e:
            raise RuntimeError(
                f"Failed reading existing Parquet from gs://{bucket_name}/{path_hierarchical}: {e}"
            ) from e

    if not existing_df.empty:
        combined = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        combined = new_df

    combined = combined.drop_duplicates(subset=["snapshot_time_utc", "symbol"], keep="last")

    buf = io.BytesIO()
    combined.to_parquet(buf, index=False, engine="pyarrow", compression="snappy")
    buf.seek(0)
    parquet_bytes = buf.getvalue()

    blob.upload_from_string(parquet_bytes, content_type="application/octet-stream")

    blob_flat = bucket.blob(path_flat)
    blob_flat.upload_from_string(parquet_bytes, content_type="application/octet-stream")

    return len(combined)
