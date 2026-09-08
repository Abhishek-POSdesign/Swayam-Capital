"""The shared option-chain feed, and the honesty of what it reports.

These exist because of a real failure on 2026-09-08: the desk re-quoted every
leg every 5 seconds, the shared cache expired after 3, so every leg on every
poll became a FYERS call. FYERS refused 46 times in ten minutes and leg prices
went blank with nothing on screen explaining why.

What is asserted here is the whole point of the fix:
  * a browser poll does not reach FYERS while the feed holds that expiry;
  * a refusal keeps the previous REAL chain and ages it honestly, rather than
    blanking it or inventing anything;
  * a refusal makes the feed stand back instead of asking again immediately;
  * with nothing cached at all, the answer is `unavailable`, never a number.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from swayam.api.chain_feed import ChainFeed


CHAIN_A = {"optionsChain": [{"option_type": "CE", "strike_price": 23500, "ltp": 120.0, "oi": 900}]}
CHAIN_B = {"optionsChain": [{"option_type": "CE", "strike_price": 23500, "ltp": 131.5, "oi": 950}]}


def make_feed(responses, *, is_open=True, **kwargs):
    """A feed over a scripted FYERS. `responses` may hold values or exceptions."""
    calls: list[tuple[str, int, str | None]] = []

    def fetch(symbol, strike_count, timestamp):
        calls.append((symbol, strike_count, timestamp))
        item = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    feed = ChainFeed(
        fetch,
        is_open=lambda: is_open,
        use_files=False,
        **kwargs,
    )
    feed.role = "leader"
    return feed, calls


def test_a_browser_poll_does_not_reach_fyers_when_the_chain_is_held() -> None:
    """The bug in one line: the poll used to outlive the cache, so it always did."""
    feed, calls = make_feed([CHAIN_A])
    key = feed.register("NSE:NIFTY50-INDEX", 50, None)

    feed.fetch_now(key)  # the cold first load, one call
    assert len(calls) == 1

    # Twenty polls, spread over longer than the old three-second cache.
    for _ in range(20):
        snap = feed.snapshot(key)
        assert snap.data == CHAIN_A

    assert len(calls) == 1, "a browser poll must never become a FYERS call"


def test_the_feed_refreshes_on_its_own_cadence_not_the_browsers() -> None:
    feed, calls = make_feed([CHAIN_A, CHAIN_B], refresh_seconds=0.0)
    feed.register("NSE:NIFTY50-INDEX", 50, None)

    asyncio.run(feed.tick())
    asyncio.run(feed.tick())

    assert len(calls) == 2
    key = ChainFeed.key_for("NSE:NIFTY50-INDEX", 50, None)
    assert feed.snapshot(key).data == CHAIN_B


def test_a_refusal_keeps_the_previous_real_chain_and_ages_it() -> None:
    """A price that is real but old is kept and labelled. Nothing is invented."""
    feed, _calls = make_feed([CHAIN_A, RuntimeError("Option chain query failed: request limit reached")],
                             refresh_seconds=0.0)
    key = feed.register("NSE:NIFTY50-INDEX", 50, None)

    asyncio.run(feed.tick())
    assert feed.snapshot(key).data == CHAIN_A

    asyncio.run(feed.tick())
    snap = feed.snapshot(key)
    assert snap.data == CHAIN_A, "the real chain we already had must survive a refusal"
    assert snap.error and "request limit" in snap.error
    assert feed.refusals == 1


def test_a_refusal_makes_the_feed_stand_back() -> None:
    refusal = RuntimeError("Option chain query failed: request limit reached")
    feed, calls = make_feed([refusal], refresh_seconds=0.0)
    feed.register("NSE:NIFTY50-INDEX", 50, None)

    asyncio.run(feed.tick())
    assert feed.backoff_until > time.time(), "it must wait before asking again"
    first = len(calls)

    # While standing back, further passes cost nothing.
    asyncio.run(feed.tick())
    asyncio.run(feed.tick())
    assert len(calls) == first

    assert "FYERS is refusing requests" in (feed.explain() or "")


def test_nothing_cached_means_unavailable_and_never_a_number() -> None:
    feed, _calls = make_feed([RuntimeError("Option chain query failed: request limit reached")],
                             refresh_seconds=0.0)
    key = feed.register("NSE:NIFTY50-INDEX", 50, None)
    asyncio.run(feed.tick())

    snap = feed.snapshot(key)
    assert snap.data is None
    assert snap.state == "unavailable"
    assert snap.as_dict()["as_of"] is None


def test_a_stale_reading_is_called_delayed_not_live() -> None:
    feed, _calls = make_feed([CHAIN_A], refresh_seconds=0.0)
    key = feed.register("NSE:NIFTY50-INDEX", 50, None)
    asyncio.run(feed.tick())

    assert feed.snapshot(key).state == "live"

    # Push the reading into the past rather than sleeping.
    feed._memory[key].fetched_at = time.time() - 90.0
    assert feed.snapshot(key).state == "delayed"


def test_after_the_close_a_reading_is_called_closing() -> None:
    feed, _calls = make_feed([CHAIN_A], is_open=False, refresh_seconds=0.0)
    key = feed.register("NSE:NIFTY50-INDEX", 50, None)
    feed.fetch_now(key)
    assert feed.snapshot(key).state == "closing"


def test_a_dead_token_says_so_in_his_language() -> None:
    feed, _calls = make_feed([RuntimeError("Please provide valid token")], refresh_seconds=0.0)
    feed.register("NSE:NIFTY50-INDEX", 50, None)
    asyncio.run(feed.tick())

    explanation = feed.explain() or ""
    assert "token" in explanation.lower()
    assert "restart" in explanation.lower()


def test_demand_expires_so_a_closed_tab_stops_costing_calls() -> None:
    feed, _calls = make_feed([CHAIN_A], demand_ttl=0.0)
    feed.register("NSE:NIFTY50-INDEX", 50, None)
    assert feed.wanted_keys() == []


@pytest.mark.parametrize(
    "message, refusing",
    [
        ("Option chain query failed: request limit reached", True),
        ("rate limit exceeded", True),
        ("Please provide valid token", False),
        ("connection reset", False),
    ],
)
def test_only_a_volume_refusal_triggers_the_backoff(message: str, refusing: bool) -> None:
    feed, _calls = make_feed([RuntimeError(message)], refresh_seconds=0.0)
    feed.register("NSE:NIFTY50-INDEX", 50, None)
    asyncio.run(feed.tick())
    assert (feed.backoff_until > time.time()) is refusing


def test_every_fyers_call_is_counted_including_the_cold_start() -> None:
    """The count is shown to him as "calls to FYERS". One that does not appear
    in it would be a lie by omission, and the cold path used to be missing."""
    feed, calls = make_feed([CHAIN_A, CHAIN_B], refresh_seconds=0.0)
    key = feed.register("NSE:NIFTY50-INDEX", 50, None)

    feed.fetch_now(key)
    assert feed.fetches == 1

    asyncio.run(feed.tick())
    assert feed.fetches == len(calls) == 2


def test_the_cold_start_does_not_immediately_refetch() -> None:
    """A cold load followed by the feed's next pass must not be two calls in a
    row for the same expiry."""
    feed, calls = make_feed([CHAIN_A, CHAIN_B], refresh_seconds=30.0)
    key = feed.register("NSE:NIFTY50-INDEX", 50, None)

    feed.fetch_now(key)
    asyncio.run(feed.tick())

    assert len(calls) == 1, "the feed must respect the interval after a cold load"


def test_a_cold_page_load_of_four_legs_is_one_fyers_call_not_four() -> None:
    """The desk asks for every leg at once. Without single-flight a cold cache
    turned one page load into one identical chain call per leg."""
    import threading as _threading

    started = _threading.Barrier(4, timeout=5)
    calls: list[str] = []

    def fetch(symbol, strike_count, timestamp):
        calls.append(symbol)
        time.sleep(0.05)  # long enough that the others are inside fetch_now
        return CHAIN_A

    feed = ChainFeed(fetch, is_open=lambda: True, use_files=False)
    feed.role = "leader"
    key = feed.register("NSE:NIFTY50-INDEX", 50, None)

    def one_leg():
        started.wait()
        feed.fetch_now(key)

    threads = [_threading.Thread(target=one_leg) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert len(calls) == 1, f"four legs must cost one chain call, not {len(calls)}"
    assert feed.fetches == 1
