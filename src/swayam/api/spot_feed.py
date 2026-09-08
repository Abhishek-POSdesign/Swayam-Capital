"""
Real NIFTY ticks over the socket that already existed.

Before this, `ws_manager.broadcast_spot()` was defined and never called from
anywhere. The socket accepted a connection and answered ping with pong, and
not one tick was ever pushed. Every price on both pages was frozen at page
load. This module is the one background task that changes that.

How it works
------------
One task per process, started from the FastAPI lifespan. During market hours
(Mon-Fri, 09:15 to 15:30 IST, and not an NSE holiday) it polls the FYERS spot
every 2 seconds and broadcasts it to every browser attached to this process.
Outside market hours it sleeps in 30-second steps and does nothing else.

Two Gunicorn workers, one FYERS call
------------------------------------
The Dockerfile runs two workers, and a browser's socket lands on whichever
worker accepted it. If both workers polled FYERS that would double the calls
for no benefit; if only one polled, the other's browsers would get nothing.
So the workers elect a leader with an advisory file lock. The leader polls
FYERS, writes each tick to a small file, and broadcasts. The follower watches
that file and broadcasts the same tick to its own browsers. One FYERS call
every 2 seconds, and every browser gets frames.

On Windows (local development, one uvicorn process) there is no `fcntl`, so
the single process is simply the leader.

Nothing here invents a price. A failed FYERS call is logged and skipped; the
browser's own watchdog falls back to a REST poll if frames stop arriving.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
from datetime import datetime, time as dtime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = dtime(9, 15)
MARKET_CLOSE = dtime(15, 30)
POLL_SECONDS = 2.0
IDLE_SECONDS = 30.0
# /tmp on the Linux container; the user's temp directory on a Windows desk.
LOCK_PATH = Path(os.getenv("SWAYAM_SPOT_LOCK_PATH", os.path.join(tempfile.gettempdir(), "swayam-spot-feed.lock")))
TICK_PATH = Path(os.getenv("SWAYAM_SPOT_TICK_PATH", os.path.join(tempfile.gettempdir(), "swayam-spot-feed.json")))


def market_is_open(now: Optional[datetime] = None) -> bool:
    """Mon-Fri, 09:15 to 15:30 IST, and not an NSE holiday."""
    from swayam.services.expiry import is_trading_day

    current = (now or datetime.now(timezone.utc)).astimezone(IST)
    if current.weekday() >= 5:
        return False
    if not is_trading_day(current.date()):
        return False
    return MARKET_OPEN <= current.time() <= MARKET_CLOSE


class SpotFeed:
    """Polls the spot while the market is open and pushes it to the browsers."""

    def __init__(
        self,
        fetch_spot: Callable[[], float],
        broadcast: Callable[[dict[str, Any]], Awaitable[None]],
        *,
        poll_seconds: float = POLL_SECONDS,
        idle_seconds: float = IDLE_SECONDS,
        is_open: Callable[[], bool] = market_is_open,
        lock_path: Path = LOCK_PATH,
        tick_path: Path = TICK_PATH,
    ) -> None:
        self.fetch_spot = fetch_spot
        self.broadcast = broadcast
        self.poll_seconds = poll_seconds
        self.idle_seconds = idle_seconds
        self.is_open = is_open
        self.lock_path = lock_path
        self.tick_path = tick_path

        self.role: Optional[str] = None  # "leader" or "follower"
        self.last_tick: Optional[dict[str, Any]] = None
        self.frames_sent = 0
        self.last_error: Optional[str] = None
        self._lock_fd: Optional[int] = None
        self._last_error_logged_at = 0.0
        self._last_seen_as_of: Optional[str] = None

    # ---------------------------------------------------------------- leader

    def elect(self) -> str:
        """Takes the advisory lock if it is free. Returns the role taken."""
        try:
            import fcntl  # type: ignore[import-not-found]
        except ImportError:
            # Windows local development: one process, so it is the leader.
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
        """The loop. Cancelled by the lifespan handler on shutdown."""
        self.elect()
        logger.info("Spot feed started as %s (pid %s).", self.role, os.getpid())
        while True:
            try:
                if not self.is_open():
                    await asyncio.sleep(self.idle_seconds)
                    continue
                if self.role == "leader":
                    await self.leader_tick()
                else:
                    await self.follower_tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - one bad tick must not kill the feed
                self._note_error(str(exc))
            await asyncio.sleep(self.poll_seconds)

    async def leader_tick(self) -> Optional[dict[str, Any]]:
        """One FYERS call, one file write, one broadcast."""
        try:
            spot = await asyncio.to_thread(self.fetch_spot)
        except Exception as exc:  # noqa: BLE001
            self._note_error(f"FYERS spot fetch failed: {exc}")
            return None
        frame = {
            "spot": float(spot),
            "as_of": datetime.now(timezone.utc).isoformat(),
            "source": "FYERS quotes, polled every 2 s",
        }
        self._write_tick(frame)
        await self._send(frame)
        return frame

    async def follower_tick(self) -> Optional[dict[str, Any]]:
        """Re-broadcasts the leader's latest tick to this process's browsers."""
        frame = self._read_tick()
        if not frame or frame.get("as_of") == self._last_seen_as_of:
            return None
        self._last_seen_as_of = frame.get("as_of")
        await self._send(frame)
        return frame

    # --------------------------------------------------------------- helpers

    async def _send(self, frame: dict[str, Any]) -> None:
        self.last_tick = frame
        self.last_error = None
        await self.broadcast(frame)
        self.frames_sent += 1

    def _write_tick(self, frame: dict[str, Any]) -> None:
        try:
            tmp = self.tick_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(frame), encoding="utf-8")
            os.replace(tmp, self.tick_path)
        except OSError as exc:
            # The leader's own browsers still get the frame; only the follower misses it.
            self._note_error(f"could not write tick file: {exc}")

    def _read_tick(self) -> Optional[dict[str, Any]]:
        try:
            return json.loads(self.tick_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def _note_error(self, message: str) -> None:
        self.last_error = message
        now = time.monotonic()
        if now - self._last_error_logged_at > 60.0:
            self._last_error_logged_at = now
            logger.warning("Spot feed: %s", message)

    def status(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "frames_sent": self.frames_sent,
            "last_tick": self.last_tick,
            "last_error": self.last_error,
            "market_open": self.is_open(),
        }
