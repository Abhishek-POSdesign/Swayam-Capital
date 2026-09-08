"""The after-hours blackout he reported himself, and the data-health answer.

His words, 2026-09-08: "when the market closes, I notice that I lose all the
prices and everything. It should not happen."

Root cause: `/api/market/expiries` kept an expiry after its day was over, so on
a weekly expiry evening the desk still offered "08 Sep (0d)". Those contracts
no longer exist and every price reads 0.05, which is what an expired option is
worth. These tests hold the fix in place.

The health tests cover the other half of what he asked for: if FYERS stops
answering while he is trading, the screen has to say so.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from swayam.api import app
from swayam.api.chain_feed import chain_feed
from swayam.api.routes import market

client = TestClient(app)


META = {
    # 08 Sep 2026 is a Tuesday and was a weekly expiry.
    "upcoming_expiries": ["2026-09-01", "2026-09-08", "2026-09-15", "2026-09-29"],
    "weekly_expiry": "2026-09-08",
    "monthly_expiry": "2026-09-29",
}


@pytest.fixture(autouse=True)
def reset_feed():
    chain_feed.reset()
    yield
    chain_feed.reset()


def freeze(monkeypatch, *, today: str, ist_hhmm: str) -> None:
    """Pins both clocks the endpoint reads, without touching the real ones."""
    frozen_today = date.fromisoformat(today)
    hh, mm = (int(x) for x in ist_hhmm.split(":"))
    # The endpoint adds 5h30m to UTC to get IST, so wind the UTC clock back.
    utc = datetime(
        frozen_today.year, frozen_today.month, frozen_today.day, hh, mm, tzinfo=timezone.utc
    ) - timedelta(hours=5, minutes=30)

    class FrozenDate(date):
        @classmethod
        def today(cls):
            return frozen_today

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return utc if tz else utc.replace(tzinfo=None)

    monkeypatch.setattr(market, "date", FrozenDate)
    monkeypatch.setattr(market, "datetime", FrozenDateTime)
    monkeypatch.setattr(market, "get_expiry_metadata", lambda: META)
    monkeypatch.setattr(market, "is_trading_day", lambda d: d.weekday() < 5)


def listed(payload) -> list[str]:
    return [e["date"] for e in payload["expiries"]]


def test_an_expiry_whose_day_has_passed_is_dropped(monkeypatch) -> None:
    freeze(monkeypatch, today="2026-09-08", ist_hhmm="11:00")
    payload = client.get("/api/market/expiries").json()
    assert "2026-09-01" not in listed(payload), "a week-old expiry must never be offered"


def test_todays_expiry_survives_until_the_bell(monkeypatch) -> None:
    """Before 15:30 it is the live front month and he may well be trading it."""
    freeze(monkeypatch, today="2026-09-08", ist_hhmm="13:30")
    payload = client.get("/api/market/expiries").json()
    assert "2026-09-08" in listed(payload)
    assert payload["weekly_expiry"] == "2026-09-08"


def test_todays_expiry_is_gone_after_the_bell(monkeypatch) -> None:
    """The exact case he hit: 17:44 on a weekly expiry, every price 0.05."""
    freeze(monkeypatch, today="2026-09-08", ist_hhmm="17:44")
    payload = client.get("/api/market/expiries").json()

    assert "2026-09-08" not in listed(payload)
    assert payload["expired_today"] == ["2026-09-01", "2026-09-08"]
    # And the desk is pointed at something that still exists.
    assert payload["weekly_expiry"] == "2026-09-15"
    assert listed(payload)[0] == "2026-09-15"


def test_the_monthly_expiry_is_untouched_when_it_is_still_live(monkeypatch) -> None:
    freeze(monkeypatch, today="2026-09-08", ist_hhmm="17:44")
    payload = client.get("/api/market/expiries").json()
    assert payload["monthly_expiry"] == "2026-09-29"


def test_the_weekly_badge_moves_to_the_expiry_that_replaced_it(monkeypatch) -> None:
    """Caught against real data: the field rolled forward but no row was flagged,
    so the dropdown would have shown no weekly at all."""
    freeze(monkeypatch, today="2026-09-08", ist_hhmm="17:44")
    payload = client.get("/api/market/expiries").json()

    flagged = [e["date"] for e in payload["expiries"] if e["is_weekly"]]
    assert flagged == ["2026-09-15"]
    assert payload["weekly_expiry"] == "2026-09-15"

    monthly_flagged = [e["date"] for e in payload["expiries"] if e["is_monthly"]]
    assert monthly_flagged == ["2026-09-29"]


def test_the_weekly_badge_stays_put_while_the_weekly_is_still_alive(monkeypatch) -> None:
    freeze(monkeypatch, today="2026-09-08", ist_hhmm="13:30")
    payload = client.get("/api/market/expiries").json()
    flagged = [e["date"] for e in payload["expiries"] if e["is_weekly"]]
    assert flagged == ["2026-09-08"]


def test_labels_still_carry_the_day_count(monkeypatch) -> None:
    freeze(monkeypatch, today="2026-09-08", ist_hhmm="17:44")
    payload = client.get("/api/market/expiries").json()
    first = payload["expiries"][0]
    assert first["label"] == "15 Sep (7d)"
    assert first["calendar_days"] == 7


# --------------------------------------------------------------- data health


def test_health_says_no_data_when_the_chain_has_never_been_read(monkeypatch) -> None:
    chain_feed.register("NSE:NIFTY50-INDEX", 50, None)
    monkeypatch.setattr(chain_feed, "last_error", "Option chain query failed: request limit reached")

    payload = client.get("/api/market/data-health").json()

    assert payload["state"] == "unavailable"
    assert payload["headline"] == "No prices from FYERS"
    assert "refusing requests" in payload["sources"]["chain"]["detail"]


def test_health_reports_the_worst_source_not_an_average(monkeypatch) -> None:
    """One glance has to be enough, so nothing hides behind a healthy sibling."""
    chain_feed.register("NSE:NIFTY50-INDEX", 50, None)
    chain_feed._store(chain_feed.key_for("NSE:NIFTY50-INDEX", 50, None), data={"optionsChain": []}, error=None)
    monkeypatch.setattr(chain_feed, "is_open", lambda: True)
    # The chain is fine; the tick feed is not running in the test app.
    payload = client.get("/api/market/data-health").json()
    assert payload["state"] in ("unavailable", "delayed")
    assert payload["sources"]["chain"]["state"] == "live"


def test_health_tells_him_what_to_do_about_a_dead_token(monkeypatch) -> None:
    chain_feed.register("NSE:NIFTY50-INDEX", 50, None)
    monkeypatch.setattr(chain_feed, "last_error", "Please provide valid token")

    payload = client.get("/api/market/data-health").json()

    assert "Refresh your FYERS token" in (payload["action"] or "")
    assert "restart" in (payload["action"] or "").lower()


def test_health_never_claims_live_when_the_market_is_shut(monkeypatch) -> None:
    monkeypatch.setattr(chain_feed, "is_open", lambda: False)
    chain_feed.register("NSE:NIFTY50-INDEX", 50, None)
    chain_feed._store(chain_feed.key_for("NSE:NIFTY50-INDEX", 50, None), data={"optionsChain": []}, error=None)

    payload = client.get("/api/market/data-health").json()

    assert payload["market_open"] is False
    assert payload["sources"]["chain"]["state"] == "closing"
    assert payload["state"] != "live"
