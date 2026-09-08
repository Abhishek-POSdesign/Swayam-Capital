"""One FYERS option-chain call per expiry per interval, however many browsers ask.

Why this exists
---------------
The desk re-quotes every leg every 5 seconds. Every one of those asks used to
reach FYERS, because the shared chain cache expired after 3 seconds, which is
less than the 5-second poll, so it never survived from one round to the next.
A four-leg structure on a far expiry cost two chain calls every five seconds,
for a single browser, sustained for as long as the page stayed open.

On 2026-09-08 that produced 46 refusals from FYERS in ten minutes
("request limit reached"), blank leg prices on the desk, and three 503s on the
spot endpoint in the same window.

What changes
------------
The browser no longer causes a FYERS call. It registers interest in an expiry
and reads whatever this feed last fetched, with the age of that reading
attached. The feed refreshes what is in demand on its own cadence, one call per
expiry however many legs or browsers are watching, and stands back when FYERS
refuses instead of asking again immediately.

Two Gunicorn workers, one FYERS call
------------------------------------
Same shape as `spot_feed.SpotFeed`, and for the same reason. The workers elect
a leader with an advisory file lock. The leader fetches and writes each chain
to a file; both workers read those files to answer requests. Demand is recorded
in a shared file so a follower's browser can ask for an expiry the leader is
not yet watching.

On Windows there is no `fcntl`, so the single local process is the leader.

Nothing here invents a price. A failed fetch keeps the previous chain and marks
it with its true age; when there is no chain at all the caller is told that,
and the screen says `unavailable` with the reason.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

# How often the leader refreshes a chain that something is watching.
REFRESH_SECONDS = 3.0
# After the close prices do not move. Keep the last real chain and re-read it
# rarely, so the desk still works in the evening without burning the budget.
CLOSED_REFRESH_SECONDS = 300.0
# An expiry nothing has asked for in this long stops being refreshed.
DEMAND_TTL_SECONDS = 90.0
# A live reading older than this is no longer described as live.
LIVE_WITHIN_SECONDS = 20.0
# Standing back after FYERS refuses.
BACKOFF_START_SECONDS = 5.0
BACKOFF_MAX_SECONDS = 120.0

_TMP = Path(os.getenv("SWAYAM_FEED_DIR", tempfile.gettempdir()))
LOCK_PATH = Path(os.getenv("SWAYAM_CHAIN_LOCK_PATH", str(_TMP / "swayam-chain-feed.lock")))
DEMAND_PATH = Path(os.getenv("SWAYAM_CHAIN_DEMAND_PATH", str(_TMP / "swayam-chain-demand.json")))
CHAIN_DIR = Path(os.getenv("SWAYAM_CHAIN_DIR", str(_TMP / "swayam-chains")))


def _is_rate_limit(message: str) -> bool:
    """FYERS refusing on volume, as opposed to any other failure.

    Kept as a substring test on purpose: FYERS returns this inside a plain
    message string rather than as a code, so there is nothing stricter to
    match on.
    """
    lowered = (message or "").lower()
    return "request limit" in lowered or "rate limit" in lowered or "too many request" in lowered


def _is_bad_token(message: str) -> bool:
    """The morning token problem, which needs a person, not a retry."""
    lowered = (message or "").lower()
    return "token" in lowered and ("invalid" in lowered or "expired" in lowered or "provide valid" in lowered)


@dataclass
class ChainSnapshot:
    """One expiry's chain, and the honest truth about how old it is."""

    key: str
    data: Optional[dict[str, Any]]
    fetched_at: Optional[float]          # epoch seconds, when FYERS answered
    error: Optional[str]                 # why the most recent attempt failed
    market_open: bool

    @property
    def age_seconds(self) -> Optional[float]:
        if self.fetched_at is None:
            return None
        return max(0.0, time.time() - self.fetched_at)

    @property
    def state(self) -> str:
        """`live`, `delayed`, `closing` or `unavailable`. Never a guess."""
        if self.data is None or self.fetched_at is None:
            return "unavailable"
        if not self.market_open:
            return "closing"
        age = self.age_seconds or 0.0
        return "live" if age <= LIVE_WITHIN_SECONDS else "delayed"

    def as_dict(self) -> dict[str, Any]:
        age = self.age_seconds
        return {
            "state": self.state,
            "as_of": (
                datetime.fromtimestamp(self.fetched_at, tz=timezone.utc).isoformat()
                if self.fetched_at
                else None
            ),
            "age_seconds": round(age, 1) if age is not None else None,
            "error": self.error,
        }


def market_is_open(now: Optional[datetime] = None) -> bool:
    """Shared with the spot feed so the two can never disagree."""
    from swayam.api.spot_feed import market_is_open as _spot_market_is_open

    return _spot_market_is_open(now)


class ChainFeed:
    """Keeps the in-demand option chains fresh, at one FYERS call each."""

    def __init__(
        self,
        fetch_chain: Callable[[str, int, Optional[str]], dict[str, Any]],
        *,
        refresh_seconds: float = REFRESH_SECONDS,
        closed_refresh_seconds: float = CLOSED_REFRESH_SECONDS,
        demand_ttl: float = DEMAND_TTL_SECONDS,
        is_open: Callable[[], bool] = market_is_open,
        lock_path: Path = LOCK_PATH,
        demand_path: Path = DEMAND_PATH,
        chain_dir: Path = CHAIN_DIR,
        use_files: Optional[bool] = None,
    ) -> None:
        self.fetch_chain = fetch_chain
        self.refresh_seconds = refresh_seconds
        self.closed_refresh_seconds = closed_refresh_seconds
        self.demand_ttl = demand_ttl
        self.is_open = is_open
        self.lock_path = lock_path
        self.demand_path = demand_path
        self.chain_dir = chain_dir
        # The files exist only to share one FYERS call between the two Gunicorn
        # workers. The test suite runs one process and must not read a chain a
        # previous run left on disk, so it turns them off with the same switch
        # that already turns off the spot feed.
        self.use_files = (
            use_files if use_files is not None else os.getenv("SWAYAM_DISABLE_SPOT_FEED") != "1"
        )

        self.role: Optional[str] = None
        self.fetches = 0
        self.refusals = 0
        self.last_error: Optional[str] = None
        self.last_error_at: Optional[float] = None
        self.backoff_until: float = 0.0
        self.backoff_seconds: float = 0.0
        self._lock_fd: Optional[int] = None
        self._local_demand: dict[str, float] = {}
        self._memory: dict[str, ChainSnapshot] = {}
        self._last_fetch_at: dict[str, float] = {}
        self._fetch_locks: dict[str, threading.Lock] = {}
        self._last_error_logged_at = 0.0

        if self.use_files:
            try:
                self.chain_dir.mkdir(parents=True, exist_ok=True)
            except OSError:  # pragma: no cover - a read-only tmp is not recoverable here
                logger.warning("Could not create the chain cache directory %s", self.chain_dir)

    def reset(self) -> None:
        """Forgets every chain, every demand and every backoff.

        For the test suite, which must not inherit a chain from the test before
        it, and for a deliberate refresh.
        """
        self._local_demand.clear()
        self._memory.clear()
        self._last_fetch_at.clear()
        self.last_error = None
        self.last_error_at = None
        self.backoff_until = 0.0
        self.backoff_seconds = 0.0
        self.fetches = 0
        self.refusals = 0
        if not self.use_files:
            return
        with contextlib.suppress(OSError):
            self.demand_path.unlink()
        with contextlib.suppress(OSError):
            for stale in self.chain_dir.glob("*.json"):
                stale.unlink()

    # ------------------------------------------------------------------ keys

    @staticmethod
    def key_for(symbol: str, strike_count: int, timestamp: Optional[str]) -> str:
        return f"{symbol}|{strike_count}|{timestamp or 'nearest'}"

    @staticmethod
    def _parse_key(key: str) -> tuple[str, int, Optional[str]]:
        symbol, count, stamp = key.split("|", 2)
        return symbol, int(count), (None if stamp == "nearest" else stamp)

    def _path_for(self, key: str) -> Path:
        safe = key.replace("|", "_").replace(":", "-").replace("/", "-")
        return self.chain_dir / f"{safe}.json"

    # ---------------------------------------------------------------- demand

    def register(self, symbol: str, strike_count: int, timestamp: Optional[str] = None) -> str:
        """Records that something wants this expiry, and returns its key.

        Cheap enough to call on every request. The write to the shared demand
        file is what lets a follower worker's browser reach the leader.
        """
        key = self.key_for(symbol, strike_count, timestamp)
        now = time.time()
        previous = self._local_demand.get(key, 0.0)
        self._local_demand[key] = now
        # Only touch the shared file when the demand is new or has gone quiet,
        # so a busy page does not rewrite it on every single request.
        if now - previous > self.demand_ttl / 3:
            self._record_shared_demand(key, now)
        return key

    def _record_shared_demand(self, key: str, now: float) -> None:
        if not self.use_files:
            return
        demand = self._read_shared_demand()
        demand[key] = now
        cutoff = now - self.demand_ttl
        demand = {k: v for k, v in demand.items() if v >= cutoff}
        try:
            tmp = self.demand_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(demand), encoding="utf-8")
            os.replace(tmp, self.demand_path)
        except OSError as exc:
            # A lost demand entry self-heals: the next browser poll re-registers.
            logger.debug("Could not write the chain demand file: %s", exc)

    def _read_shared_demand(self) -> dict[str, float]:
        if not self.use_files:
            return {}
        try:
            raw = json.loads(self.demand_path.read_text(encoding="utf-8"))
            return {str(k): float(v) for k, v in raw.items()}
        except (OSError, ValueError, TypeError):
            return {}

    def wanted_keys(self) -> list[str]:
        """Everything asked for recently, by this worker or the other one."""
        now = time.time()
        cutoff = now - self.demand_ttl
        merged: dict[str, float] = {k: v for k, v in self._local_demand.items() if v >= cutoff}
        for k, v in self._read_shared_demand().items():
            if v >= cutoff and v > merged.get(k, 0.0):
                merged[k] = v
        return sorted(merged, key=lambda k: merged[k], reverse=True)

    # ----------------------------------------------------------------- reads

    def snapshot(self, key: str) -> ChainSnapshot:
        """The freshest chain this process can see for that key.

        Never calls FYERS. Prefers whatever is newer between this process's own
        memory and the file the leader writes.
        """
        open_now = self.is_open()
        mine = self._memory.get(key)
        theirs = self._read_chain_file(key)
        best = mine
        if theirs and (not mine or (theirs.fetched_at or 0) > (mine.fetched_at or 0)):
            best = theirs
        if best is None:
            return ChainSnapshot(key=key, data=None, fetched_at=None, error=self.last_error, market_open=open_now)
        return ChainSnapshot(
            key=key,
            data=best.data,
            fetched_at=best.fetched_at,
            error=best.error or (self.last_error if best.data is None else None),
            market_open=open_now,
        )

    def fetch_now(self, key: str) -> dict[str, Any]:
        """One inline FYERS call, for a cold cache only.

        The first page load of the day has nothing to read, and a blank desk
        while waiting for the feed's first pass would be worse than one call.

        Single-flight, because the desk asks for all four legs at once: without
        the lock a cold cache turned one page load into four identical chain
        calls, which is the same waste this whole module exists to remove.
        The second caller through the door waits and then reads the cache.

        Raises whatever FYERS raises; nothing is substituted.
        """
        lock = self._fetch_locks.setdefault(key, threading.Lock())
        with lock:
            existing = self._memory.get(key) or self._read_chain_file(key)
            if existing is not None and existing.data is not None:
                return existing.data
            symbol, strike_count, timestamp = self._parse_key(key)
            data = self.fetch_chain(symbol, strike_count, timestamp)
            # Counted like any other, because this number is shown to him as
            # "calls to FYERS", and one missing from it is a lie by omission.
            self.fetches += 1
            self._last_fetch_at[key] = time.time()
            self._store(key, data=data, error=None)
            return data

    # ------------------------------------------------------------------ loop

    def elect(self) -> str:
        try:
            import fcntl  # type: ignore[import-not-found]
        except ImportError:
            self.role = "leader"
            return self.role
        try:
            fd = os.open(str(self.lock_path), os.O_RDWR | os.O_CREAT, 0o644)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd = fd
            self.role = "leader"
        except OSError:
            self.role = "follower"
        return self.role

    async def run(self) -> None:
        """Refreshes what is in demand. Cancelled by the lifespan handler."""
        self.elect()
        logger.info("Chain feed started as %s (pid %s).", self.role, os.getpid())
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - one bad pass must not kill the feed
                self._note_error(str(exc))
            await asyncio.sleep(1.0)

    async def tick(self) -> int:
        """One pass over the in-demand expiries. Returns how many were fetched."""
        if self.role != "leader":
            return 0
        now = time.time()
        if now < self.backoff_until:
            return 0
        open_now = self.is_open()
        interval = self.refresh_seconds if open_now else self.closed_refresh_seconds
        fetched = 0
        for key in self.wanted_keys():
            if time.time() - self._last_fetch_at.get(key, 0.0) < interval:
                continue
            if not await self._refresh(key):
                break  # FYERS refused; stop this pass rather than repeat it per expiry
            fetched += 1
        return fetched

    async def _refresh(self, key: str) -> bool:
        """Fetches one expiry. Returns False when FYERS refused."""
        symbol, strike_count, timestamp = self._parse_key(key)
        self._last_fetch_at[key] = time.time()
        try:
            data = await asyncio.to_thread(self.fetch_chain, symbol, strike_count, timestamp)
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            self._note_error(message)
            # Keep the previous chain. It is real, it is simply older, and the
            # age travels with it to the screen.
            self._store(key, data=None, error=message, keep_previous=True)
            if _is_rate_limit(message):
                self.refusals += 1
                self.backoff_seconds = min(
                    BACKOFF_MAX_SECONDS,
                    max(BACKOFF_START_SECONDS, self.backoff_seconds * 2 or BACKOFF_START_SECONDS),
                )
                self.backoff_until = time.time() + self.backoff_seconds
                logger.warning(
                    "FYERS refused on volume; standing back for %.0f s before the next chain read.",
                    self.backoff_seconds,
                )
            return False
        self.fetches += 1
        self.backoff_seconds = 0.0
        self.backoff_until = 0.0
        self.last_error = None
        self._store(key, data=data, error=None)
        return True

    # --------------------------------------------------------------- storage

    def _store(
        self,
        key: str,
        *,
        data: Optional[dict[str, Any]],
        error: Optional[str],
        keep_previous: bool = False,
    ) -> None:
        if data is None and keep_previous:
            existing = self._memory.get(key) or self._read_chain_file(key)
            if existing is not None and existing.data is not None:
                snap = ChainSnapshot(
                    key=key,
                    data=existing.data,
                    fetched_at=existing.fetched_at,
                    error=error,
                    market_open=self.is_open(),
                )
                self._memory[key] = snap
                self._write_chain_file(snap)
                return
        snap = ChainSnapshot(
            key=key,
            data=data,
            fetched_at=time.time() if data is not None else None,
            error=error,
            market_open=self.is_open(),
        )
        self._memory[key] = snap
        if data is not None:
            self._write_chain_file(snap)

    def _write_chain_file(self, snap: ChainSnapshot) -> None:
        if not self.use_files:
            return
        path = self._path_for(snap.key)
        payload = {"fetched_at": snap.fetched_at, "error": snap.error, "data": snap.data}
        try:
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            # The leader's own requests still see it; only the follower misses out.
            logger.debug("Could not write the chain cache file for %s: %s", snap.key, exc)

    def _read_chain_file(self, key: str) -> Optional[ChainSnapshot]:
        if not self.use_files:
            return None
        try:
            raw = json.loads(self._path_for(key).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return ChainSnapshot(
            key=key,
            data=raw.get("data"),
            fetched_at=raw.get("fetched_at"),
            error=raw.get("error"),
            market_open=self.is_open(),
        )

    # ---------------------------------------------------------------- health

    def _note_error(self, message: str) -> None:
        self.last_error = message
        self.last_error_at = time.time()
        now = time.monotonic()
        if now - self._last_error_logged_at > 60.0:
            self._last_error_logged_at = now
            logger.warning("Chain feed: %s", message)

    def explain(self) -> Optional[str]:
        """The current failure in his language, or None when nothing is wrong."""
        if not self.last_error:
            return None
        if _is_rate_limit(self.last_error):
            wait = max(0.0, self.backoff_until - time.time())
            return (
                "FYERS is refusing requests because too many were sent. "
                f"Waiting {wait:.0f} seconds before asking again."
            )
        if _is_bad_token(self.last_error):
            return (
                "FYERS rejected the access token. Refresh it and restart the service, "
                "otherwise prices will not return on their own."
            )
        return f"FYERS could not be read: {self.last_error}"

    def status(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "watching": self.wanted_keys(),
            "fetches": self.fetches,
            "refusals": self.refusals,
            "backoff_seconds_remaining": round(max(0.0, self.backoff_until - time.time()), 1),
            "last_error": self.last_error,
            "explanation": self.explain(),
            "market_open": self.is_open(),
        }


def _default_fetch(symbol: str, strike_count: int, timestamp: Optional[str]) -> dict[str, Any]:
    from swayam.fyers_client import fyers_client

    return fyers_client.get_option_chain(underlying=symbol, strike_count=strike_count, timestamp=timestamp)


chain_feed = ChainFeed(_default_fetch)
