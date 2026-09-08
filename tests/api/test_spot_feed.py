"""
Real ticks over the socket that already existed.

Before this, `broadcast_spot()` was never called from anywhere. These tests
prove that frames are produced, that only the leader calls FYERS, that a
follower re-broadcasts the leader's tick without its own FYERS call, and that
nothing is sent outside market hours.
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from swayam.api import spot_feed
from swayam.api.spot_feed import SpotFeed, market_is_open

IST = ZoneInfo("Asia/Kolkata")


def test_market_hours_are_weekdays_0915_to_1530_ist_and_not_holidays():
    assert market_is_open(datetime(2026, 9, 9, 11, 0, tzinfo=IST)) is True  # Wednesday
    assert market_is_open(datetime(2026, 9, 9, 9, 14, tzinfo=IST)) is False
    assert market_is_open(datetime(2026, 9, 9, 15, 31, tzinfo=IST)) is False
    assert market_is_open(datetime(2026, 9, 12, 11, 0, tzinfo=IST)) is False  # Saturday
    assert market_is_open(datetime(2026, 10, 2, 11, 0, tzinfo=IST)) is False  # Gandhi Jayanti


def test_leader_polls_fyers_and_broadcasts_a_real_frame(tmp_path):
    sent = []

    async def broadcast(frame):
        sent.append(frame)

    feed = SpotFeed(
        fetch_spot=lambda: 24867.5,
        broadcast=broadcast,
        is_open=lambda: True,
        lock_path=tmp_path / "lock",
        tick_path=tmp_path / "tick.json",
    )
    feed.role = "leader"
    frame = asyncio.run(feed.leader_tick())

    assert frame["spot"] == 24867.5
    assert "as_of" in frame
    assert sent == [frame]
    assert feed.frames_sent == 1
    assert feed.last_tick == frame
    assert (tmp_path / "tick.json").exists()


def test_follower_rebroadcasts_the_leaders_tick_without_calling_fyers(tmp_path):
    leader_sent, follower_sent = [], []

    async def leader_broadcast(frame):
        leader_sent.append(frame)

    async def follower_broadcast(frame):
        follower_sent.append(frame)

    def must_not_call():
        raise AssertionError("the follower must never call FYERS")

    leader = SpotFeed(lambda: 24900.0, leader_broadcast, is_open=lambda: True,
                      lock_path=tmp_path / "lock", tick_path=tmp_path / "tick.json")
    leader.role = "leader"
    follower = SpotFeed(must_not_call, follower_broadcast, is_open=lambda: True,
                        lock_path=tmp_path / "lock", tick_path=tmp_path / "tick.json")
    follower.role = "follower"

    asyncio.run(leader.leader_tick())
    first = asyncio.run(follower.follower_tick())
    again = asyncio.run(follower.follower_tick())

    assert first is not None and first["spot"] == 24900.0
    assert again is None  # the same tick is not sent twice
    assert follower_sent == [first]


def test_a_failed_fyers_call_is_reported_and_no_frame_is_invented(tmp_path):
    sent = []

    async def broadcast(frame):
        sent.append(frame)

    def broken():
        raise RuntimeError("Please provide valid token")

    feed = SpotFeed(broken, broadcast, is_open=lambda: True,
                    lock_path=tmp_path / "lock", tick_path=tmp_path / "tick.json")
    feed.role = "leader"
    assert asyncio.run(feed.leader_tick()) is None
    assert sent == []
    assert "valid token" in feed.last_error


def test_the_loop_sleeps_outside_market_hours_and_polls_inside(tmp_path):
    """A closed market means no FYERS call at all; an open one means a frame."""
    calls = []
    sent = []

    async def broadcast(frame):
        sent.append(frame)

    def fetch():
        calls.append(1)
        return 25000.0

    async def run_for(feed, seconds):
        task = asyncio.create_task(feed.run())
        await asyncio.sleep(seconds)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    closed = SpotFeed(fetch, broadcast, poll_seconds=0.01, idle_seconds=0.01, is_open=lambda: False,
                      lock_path=tmp_path / "lock", tick_path=tmp_path / "tick.json")
    asyncio.run(run_for(closed, 0.1))
    assert calls == [] and sent == []

    open_ = SpotFeed(fetch, broadcast, poll_seconds=0.01, idle_seconds=0.01, is_open=lambda: True,
                     lock_path=tmp_path / "lock", tick_path=tmp_path / "tick.json")
    asyncio.run(run_for(open_, 0.1))
    assert len(calls) >= 2
    assert len(sent) == len(calls)
    assert open_.role == "leader"


def test_the_app_is_wired_to_start_the_feed_from_its_lifespan():
    """`broadcast_spot` used to be defined and never called. Now main.py calls it."""
    import inspect
    from swayam.api import main

    src = inspect.getsource(main)
    assert "SpotFeed(" in src
    assert "ws_manager.broadcast_spot" in src
    assert "lifespan=lifespan" in src


def test_ws_manager_broadcast_reaches_every_connection():
    from swayam.api.ws_manager import WebSocketManager

    class FakeWs:
        def __init__(self):
            self.frames = []

        async def send_json(self, frame):
            self.frames.append(frame)

    mgr = WebSocketManager()
    a, b = FakeWs(), FakeWs()
    mgr.active_spot_connections.extend([a, b])
    asyncio.run(mgr.broadcast_spot({"spot": 1.0}))
    assert a.frames == [{"spot": 1.0}] and b.frames == [{"spot": 1.0}]
