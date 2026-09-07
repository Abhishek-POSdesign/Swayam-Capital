"""
The FYERS contract master, as the single source of truth for contract size.

Why this module exists
----------------------
The NIFTY lot size is **65**. This platform hardcoded **75** in twenty-four
places across the backend and the frontend. Every rupee figure scaled by number
of contracts was therefore 15.4% too large: total premium, net debit and credit,
payoff curves, max profit, max loss, the stressed loss, position P&L, margin and
charges. Per-unit quotes were never affected.

The correct value was already sitting on disk. `NSE_FO.csv`, which this app
downloads for expiry dates, carries the lot size in column index 3, and it reads
65 on all 3,935 NIFTY rows. Nobody read it.

The rule this module enforces: **a missing lot size blocks the trade.** There is
no default and no fallback. A wrong contract size is worse than no trade.

Column layout of NSE_FO.csv, verified 2026-09-07:
    0  fytoken            9  exchange symbol
    1  description       13  underlying symbol   (e.g. NIFTY)
    3  LOT SIZE          15  strike price
    4  tick size         16  option type         (CE / PE / XX for futures)
    8  expiry, epoch seconds
"""

from __future__ import annotations

import csv
import logging
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Kolkata"
FYERS_NSE_FO_URL = "https://public.fyers.in/sym_details/NSE_FO.csv"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CACHE_FILE = REPO_ROOT / "data" / "NSE_FO_cache.csv"

COL_LOT_SIZE = 3
COL_EXPIRY_EPOCH = 8
COL_UNDERLYING = 13
COL_OPTION_TYPE = 16

_CACHE_SECONDS = 6 * 3600

# (fetched_at, csv text)
_cached_csv: Optional[tuple[datetime, str]] = None
# (built_at, {(underlying, expiry): lot_size})
_cached_lots: Optional[tuple[datetime, dict[tuple[str, date], int]]] = None


class ContractMasterUnavailable(RuntimeError):
    """The contract master could not be fetched or read.

    This is deliberately a hard failure. Anything that needs a contract size
    must stop rather than guess one.
    """


def load_contract_master(*, force: bool = False) -> str:
    """Returns the contract master CSV, from memory, disk, or FYERS.

    Raises ContractMasterUnavailable if every source fails. It never returns
    empty or partial text.
    """
    global _cached_csv

    now = datetime.now()
    if not force and _cached_csv is not None:
        fetched_at, text = _cached_csv
        if (now - fetched_at).total_seconds() < _CACHE_SECONDS:
            return text

    text: Optional[str] = None
    try:
        req = urllib.request.Request(
            FYERS_NSE_FO_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8")
        try:
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            CACHE_FILE.write_text(text, encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not write contract master disk cache: %s", exc)
    except Exception as exc:
        logger.warning("Could not fetch FYERS contract master: %s", exc)
        if CACHE_FILE.exists():
            try:
                text = CACHE_FILE.read_text(encoding="utf-8")
                logger.warning("Using the contract master disk cache instead.")
            except OSError as read_exc:
                logger.error("Could not read contract master disk cache: %s", read_exc)

    if not text or not text.strip():
        raise ContractMasterUnavailable(
            "The FYERS contract master could not be fetched and no usable cache "
            "exists. Contract size is unknown, so no trade can be priced."
        )

    _cached_csv = (now, text)
    return text


def _lot_size_map(*, force: bool = False) -> dict[tuple[str, date], int]:
    """Builds {(underlying, expiry): lot size} from the contract master.

    Keyed by expiry because a SEBI lot-size revision takes effect from a future
    expiry, so two different lot sizes legitimately coexist in one file.
    """
    global _cached_lots

    now = datetime.now()
    if not force and _cached_lots is not None:
        built_at, table = _cached_lots
        if (now - built_at).total_seconds() < _CACHE_SECONDS:
            return table

    tz = ZoneInfo(TIMEZONE)
    table: dict[tuple[str, date], int] = {}
    for row in csv.reader(load_contract_master(force=force).splitlines()):
        if len(row) <= COL_OPTION_TYPE:
            continue
        if row[COL_OPTION_TYPE] not in ("CE", "PE"):
            continue
        try:
            lot = int(row[COL_LOT_SIZE])
            expiry = datetime.fromtimestamp(int(row[COL_EXPIRY_EPOCH]), tz=tz).date()
        except (ValueError, IndexError, OSError):
            continue
        if lot <= 0:
            continue
        table[(row[COL_UNDERLYING].strip().upper(), expiry)] = lot

    if not table:
        raise ContractMasterUnavailable(
            "The contract master was read but contained no option contracts. "
            "Contract size is unknown, so no trade can be priced."
        )

    _cached_lots = (now, table)
    return table


def get_lot_size(underlying: str = "NIFTY", expiry: Optional[date] = None) -> int:
    """Returns the contract size for an underlying, for a given expiry.

    Args:
        underlying: e.g. "NIFTY".
        expiry: the contract's expiry. When omitted, the nearest expiry that is
            not in the past is used, falling back to the latest known expiry.

    Raises:
        ContractMasterUnavailable: if no contract size can be established.
            Callers must let this stop the trade. Never substitute a number.
    """
    key_underlying = underlying.strip().upper()
    table = _lot_size_map()

    if expiry is not None:
        lot = table.get((key_underlying, expiry))
        if lot is not None:
            return lot
        # An expiry we do not carry is not a reason to guess. Fall through to
        # the nearest expiry only when every contract for this underlying
        # agrees on the size, which is the ordinary case.
        sizes = {v for (u, _), v in table.items() if u == key_underlying}
        if len(sizes) == 1:
            return sizes.pop()
        raise ContractMasterUnavailable(
            f"No contract size for {key_underlying} expiring {expiry:%Y-%m-%d}, "
            f"and this underlying has more than one lot size in force "
            f"({sorted(sizes)}). Refusing to guess."
        )

    expiries = sorted(e for (u, e) in table if u == key_underlying)
    if not expiries:
        raise ContractMasterUnavailable(
            f"The contract master carries no option contracts for {key_underlying}."
        )
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    upcoming = [e for e in expiries if e >= today]
    return table[(key_underlying, upcoming[0] if upcoming else expiries[-1])]


def describe(underlying: str = "NIFTY") -> dict:
    """Contract size with its provenance, for display and for the API.

    Every number this platform shows must be able to say where it came from.
    """
    table = _lot_size_map()
    today = datetime.now(ZoneInfo(TIMEZONE)).date()
    key = underlying.strip().upper()
    sizes = sorted({v for (u, _), v in table.items() if u == key})
    contracts = sum(1 for (u, _) in table if u == key)
    source_age = None
    if CACHE_FILE.exists():
        source_age = datetime.fromtimestamp(CACHE_FILE.stat().st_mtime).isoformat()
    return {
        "underlying": key,
        "lot_size": get_lot_size(key),
        "lot_sizes_in_force": sizes,
        "expiries_seen": contracts,
        "source": "FYERS contract master NSE_FO.csv, column 3",
        "source_url": FYERS_NSE_FO_URL,
        "source_fetched_at": source_age,
        "as_of": today.isoformat(),
    }


def get_symbol(
    underlying: str,
    expiry: date,
    strike: float,
    option_type: str,
) -> str:
    """Returns the FYERS exchange symbol for one option contract.

    Read from the contract master rather than assembled from a format string,
    because the symbol encoding differs between weekly and monthly expiries and
    a hand-built symbol is a silent source of wrong quotes and wrong margin.

    Raises:
        ContractMasterUnavailable: if no such contract exists.
    """
    key = (underlying.strip().upper(), expiry, float(strike), option_type.strip().upper())
    symbol = _symbol_map().get(key)
    if symbol is None:
        raise ContractMasterUnavailable(
            f"No contract in the FYERS master for {key[0]} {key[3]} {key[2]:g} "
            f"expiring {expiry:%Y-%m-%d}."
        )
    return symbol


# (built_at, {(underlying, expiry, strike, option_type): symbol})
_cached_symbols: Optional[tuple[datetime, dict[tuple[str, date, float, str], str]]] = None

COL_SYMBOL = 9
COL_STRIKE = 15


def _symbol_map(*, force: bool = False) -> dict[tuple[str, date, float, str], str]:
    global _cached_symbols

    now = datetime.now()
    if not force and _cached_symbols is not None:
        built_at, table = _cached_symbols
        if (now - built_at).total_seconds() < _CACHE_SECONDS:
            return table

    tz = ZoneInfo(TIMEZONE)
    table: dict[tuple[str, date, float, str], str] = {}
    for row in csv.reader(load_contract_master(force=force).splitlines()):
        if len(row) <= COL_OPTION_TYPE:
            continue
        opt = row[COL_OPTION_TYPE]
        if opt not in ("CE", "PE"):
            continue
        try:
            expiry = datetime.fromtimestamp(int(row[COL_EXPIRY_EPOCH]), tz=tz).date()
            strike = float(row[COL_STRIKE])
        except (ValueError, IndexError, OSError):
            continue
        table[(row[COL_UNDERLYING].strip().upper(), expiry, strike, opt)] = row[COL_SYMBOL]

    if not table:
        raise ContractMasterUnavailable(
            "The contract master carries no option symbols."
        )
    _cached_symbols = (now, table)
    return table
