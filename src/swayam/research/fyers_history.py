"""Downloading history from FYERS, gently and honestly.

Two separate routes, because FYERS treats them as two separate things:

- `candles()` is the ordinary history API. It serves the NIFTY index back to
  January 2018 at one minute and at least 2010 daily, and it serves option
  contracts only while they are still listed. Ask it for an expired contract and
  it answers `Invalid symbol provided`.
- `expired_*()` are the expired F&O endpoints, which are not in the version of
  `fyers-apiv3` this repository installs (3.1.5; they appear in 3.1.17). They are
  called here with plain `requests` on purpose. **Do not upgrade the package to
  reach them.** That package is what the live execution ticket runs on, and
  changing it is its own piece of work on its own day.

The request budget is shared with the live terminal
---------------------------------------------------
Every call here spends from the same FYERS allowance the desk uses to quote his
legs. On 2026-09-08 an unthrottled desk produced 46 refusals in ten minutes and
blank prices on his screen. So this module paces itself, backs off when refused,
and `scripts/` refuses to run it inside his trading window without `--force`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta, timezone
import logging
import time
from typing import Any, Iterator, Optional
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
DATA_BASE = "https://api-t1.fyers.in/data"

# FYERS refuses a span longer than these. Measured, not documented: a 250-day
# one-minute request and a 980-day daily request both return "Invalid input".
MAX_DAYS_MINUTE = 90
MAX_DAYS_DAILY = 360

# His window is 13:00 to 15:30 IST and the desk quotes every five seconds inside
# it. Nothing bulk runs then.
HIS_WINDOW_START = dtime(12, 30)
HIS_WINDOW_END = dtime(15, 45)

DEFAULT_PAUSE_SECONDS = 0.4
BACKOFF_START_SECONDS = 5.0
BACKOFF_MAX_SECONDS = 120.0


class FyersHistoryError(RuntimeError):
    """FYERS refused, and the caller has to decide what that means."""


def in_his_trading_window(now: Optional[datetime] = None) -> bool:
    """True while he could be at the desk, when nothing bulk may run."""
    local = (now or datetime.now(timezone.utc)).astimezone(IST)
    if local.weekday() >= 5:
        return False
    return HIS_WINDOW_START <= local.time() <= HIS_WINDOW_END


def date_chunks(start: date, end: date, max_days: int) -> Iterator[tuple[date, date]]:
    """Splits a span into pieces FYERS will accept, oldest first."""
    cursor = start
    while cursor <= end:
        stop = min(cursor + timedelta(days=max_days - 1), end)
        yield cursor, stop
        cursor = stop + timedelta(days=1)


@dataclass
class FyersHistory:
    """A paced, backing-off client for the two history routes."""

    app_id: str
    access_token: str
    pause_seconds: float = DEFAULT_PAUSE_SECONDS
    session: requests.Session = field(default_factory=requests.Session)
    calls: int = 0
    refusals: int = 0

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"{self.app_id}:{self.access_token}",
            "Content-Type": "application/json",
            "version": "3",
        }

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        backoff = BACKOFF_START_SECONDS
        while True:
            self.calls += 1
            response = self.session.get(
                DATA_BASE + path, headers=self.headers, params=params, timeout=60
            )
            try:
                body = response.json()
            except ValueError as exc:
                raise FyersHistoryError(
                    f"FYERS returned something that is not JSON from {path}: "
                    f"HTTP {response.status_code}"
                ) from exc

            message = str(body.get("message") or "")
            if _is_rate_limit(message) or response.status_code == 429:
                self.refusals += 1
                logger.warning(
                    "FYERS refused on volume (%s). Standing back %.0fs.", message, backoff
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, BACKOFF_MAX_SECONDS)
                continue

            if _is_bad_token(message):
                # A retry cannot fix this and hammering it will not help.
                raise FyersHistoryError(
                    f"FYERS rejected the access token: {message}. "
                    "Refresh it with .\\Refresh-Token.ps1 and run this again; "
                    "the download resumes where it stopped."
                )

            time.sleep(self.pause_seconds)
            return body

    # ------------------------------------------------------- ordinary history

    def candles(
        self, symbol: str, resolution: str, range_from: date, range_to: date
    ) -> list[list[float]]:
        """Candles for a LISTED symbol. `[]` when FYERS has none for the span."""
        body = self._get(
            "/history",
            {
                "symbol": symbol,
                "resolution": resolution,
                "date_format": "1",
                "range_from": range_from.isoformat(),
                "range_to": range_to.isoformat(),
                "cont_flag": "1",
            },
        )
        status = body.get("s")
        if status == "no_data":
            return []
        if status != "ok":
            raise FyersHistoryError(
                f"FYERS refused history for {symbol} {range_from}..{range_to}: "
                f"{body.get('message') or body}"
            )
        return body.get("candles") or []

    # ------------------------------------------------------- expired contracts

    def expired_expiry_dates(
        self, underlying: str, range_from: date, range_to: date
    ) -> dict[str, list[str]]:
        """Every expiry FYERS lists in the span, as `{"options": [...], "futures": [...]}`."""
        body = self._get(
            "/history/fno/expired/expiry-dates",
            {
                "symbol": underlying,
                "range_from": range_from.isoformat(),
                "range_to": range_to.isoformat(),
                "date_format": 1,
            },
        )
        if body.get("s") != "ok":
            raise FyersHistoryError(
                f"FYERS refused expiry dates for {underlying}: {body.get('message') or body}"
            )
        return (body.get("data") or {}).get("expiry_dates") or {}

    def expired_contracts(self, underlying: str, expiry: date) -> list[str]:
        """Every option contract that existed for one expiry."""
        body = self._get(
            "/history/fno/expired/underlying-symbols",
            {"symbol": underlying, "expiry_date": expiry.isoformat()},
        )
        if body.get("s") != "ok":
            raise FyersHistoryError(
                f"FYERS refused contracts for {underlying} {expiry}: {body.get('message') or body}"
            )
        return ((body.get("data") or {}).get("contracts") or {}).get("options") or []

    def expired_candles(
        self, symbol: str, resolution: str, range_from: date, range_to: date
    ) -> list[list[float]]:
        """Candles for an EXPIRED contract. `[]` when FYERS holds none.

        Six values a candle: epoch, open, high, low, close, volume. There is no
        open interest, no implied volatility, no Greeks and no bid or ask,
        whatever `greeks` is set to. Tested both ways on 2026-09-09: the two
        replies were byte-identical.
        """
        body = self._get(
            "/history/fno/expired/historical-data",
            {
                "symbol": symbol,
                "resolution": resolution,
                "date_format": 1,
                "range_from": range_from.isoformat(),
                "range_to": range_to.isoformat(),
                "greeks": 1,
            },
        )
        status = body.get("s")
        if status == "no_data":
            return []
        if status != "ok":
            raise FyersHistoryError(
                f"FYERS refused expired candles for {symbol}: {body.get('message') or body}"
            )
        return body.get("candles") or []


def _is_rate_limit(message: str) -> bool:
    lowered = (message or "").lower()
    return any(
        phrase in lowered
        for phrase in ("request limit", "rate limit", "too many request")
    )


def _is_bad_token(message: str) -> bool:
    lowered = (message or "").lower()
    return "token" in lowered and any(
        word in lowered for word in ("invalid", "expired", "provide valid")
    )
