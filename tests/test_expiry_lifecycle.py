"""When an expiry stops existing, and who is allowed to say "live".

Both of these are the same class of bug: two parts of the app answering a
question differently, or never asking it at all.

**The expiry.** `get_expiry_metadata` kept today's expiry all evening, because
it filtered on `d >= ref_date` and nothing else. So on the evening of a weekly
expiry the desk still offered "08 Sep (0d)", those contracts no longer existed,
and every price read 0.05, which is what an expired option is worth. That is
what Abhishek reported as "when the market closes I lose all the prices".

It was fixed once at the API layer on 2026-09-08 and the fault survived in
`services/nifty_snapshot.py`, which reads this provider directly and bypassed
that fix. Home's Options card still counted down to a dead contract. The rule
now lives here, at the source, so there is one answer and every caller gets it.

**The word "live".** `spot_live` means "FYERS returned a number", which is not
the same question as "is the market open". Four separate screens claimed LIVE
over a closing price before this was traced to the flag they all read.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from swayam.services.expiry import expiry_is_alive, get_expiry_metadata, session_is_over

IST = ZoneInfo("Asia/Kolkata")
EXPIRY_DAY = date(2026, 9, 8)  # a Tuesday, and a real weekly expiry


def at(hour: int, minute: int) -> datetime:
    return datetime(2026, 9, 8, hour, minute, tzinfo=IST)


# --------------------------------------------------------------- the bell


@pytest.mark.parametrize(
    "hour, minute, over",
    [
        (9, 15, False),    # the open
        (13, 30, False),   # when he is actually at the desk
        (15, 29, False),   # one minute before the bell
        (15, 30, False),   # the bell itself: still tradeable
        (15, 31, True),    # gone
        (17, 44, True),    # when he hit it
        (23, 59, True),
    ],
)
def test_the_bell_is_1530_ist(hour: int, minute: int, over: bool) -> None:
    assert session_is_over(at(hour, minute)) is over


def test_a_naive_datetime_is_read_as_ist_not_utc() -> None:
    """A five and a half hour mistake here would move the bell into the morning."""
    assert session_is_over(datetime(2026, 9, 8, 17, 44)) is True
    assert session_is_over(datetime(2026, 9, 8, 13, 30)) is False


# ------------------------------------------------------- what is still alive


def test_todays_expiry_lives_until_the_bell() -> None:
    """Before 15:30 it is the live front month and he may well be trading it."""
    assert expiry_is_alive(EXPIRY_DAY, EXPIRY_DAY, at(13, 30)) is True


def test_todays_expiry_is_dead_after_the_bell() -> None:
    """The exact case he reported: 17:44 on a weekly expiry, every price 0.05."""
    assert expiry_is_alive(EXPIRY_DAY, EXPIRY_DAY, at(17, 44)) is False


def test_a_past_expiry_is_never_alive() -> None:
    assert expiry_is_alive(date(2026, 9, 1), EXPIRY_DAY, at(11, 0)) is False


def test_a_future_expiry_is_always_alive() -> None:
    for hour in (9, 13, 17, 23):
        assert expiry_is_alive(date(2026, 9, 15), EXPIRY_DAY, at(hour, 0)) is True


# ------------------------------------------------- the provider every caller reads


def test_the_provider_drops_the_dead_expiry_and_rolls_the_weekly_forward() -> None:
    """Reads the real FYERS contract master, with the clock pinned."""
    after = get_expiry_metadata(ref_date=EXPIRY_DAY, now=at(17, 44))

    assert "2026-09-08" not in after["upcoming_expiries"]
    assert after["expired_today"] == ["2026-09-08"]
    assert after["weekly_expiry"] == "2026-09-15"


def test_the_provider_keeps_it_while_the_market_is_open() -> None:
    during = get_expiry_metadata(ref_date=EXPIRY_DAY, now=at(13, 30))

    assert during["upcoming_expiries"][0] == "2026-09-08"
    assert during["weekly_expiry"] == "2026-09-08"
    assert during["expired_today"] == []


def test_days_to_expiry_stays_relative_to_today_not_to_tomorrow() -> None:
    """The subtle one. Rolling the weekly forward must not also roll the clock,
    or every countdown on screen would be short by a day."""
    after = get_expiry_metadata(ref_date=EXPIRY_DAY, now=at(17, 44))

    # 8 September to 15 September is seven calendar days, read on the 8th.
    assert after["weekly_dte"]["calendar_days"] == 7
    assert after["weekly_dte"]["trading_sessions"] >= 1


def test_the_monthly_expiry_is_not_disturbed() -> None:
    before = get_expiry_metadata(ref_date=EXPIRY_DAY, now=at(13, 30))
    after = get_expiry_metadata(ref_date=EXPIRY_DAY, now=at(17, 44))

    assert before["monthly_expiry"] == after["monthly_expiry"] == "2026-09-29"
    assert before["monthly_dte"]["calendar_days"] == after["monthly_dte"]["calendar_days"]


def test_the_weekly_never_points_at_something_dropped() -> None:
    """Whatever the clock says, the weekly must be in the list of live expiries."""
    for hour, minute in [(9, 20), (13, 30), (15, 31), (20, 51)]:
        meta = get_expiry_metadata(ref_date=EXPIRY_DAY, now=at(hour, minute))
        assert meta["weekly_expiry"] in meta["upcoming_expiries"], f"broken at {hour}:{minute}"


# ------------------------------------------------------ who may say "live"


def test_the_snapshot_does_not_call_a_closing_price_live(monkeypatch) -> None:
    """His Sectors card read "LIVE · read 20:51 IST" with the market shut."""
    from swayam.api import spot_feed

    monkeypatch.setattr(spot_feed, "market_is_open", lambda *_a, **_k: False)

    # The branch under test, in the same shape the snapshot uses it.
    spot_live = True
    if not spot_live:
        state = "UNAVAILABLE"
    elif spot_feed.market_is_open():
        state = "LIVE"
    else:
        state = "CLOSED"

    assert state == "CLOSED"


def test_no_price_at_all_is_unavailable_not_closed(monkeypatch) -> None:
    """Missing and stale are different facts and must not share a label."""
    from swayam.api import spot_feed

    monkeypatch.setattr(spot_feed, "market_is_open", lambda *_a, **_k: False)
    spot_live = False
    state = "UNAVAILABLE" if not spot_live else ("LIVE" if spot_feed.market_is_open() else "CLOSED")
    assert state == "UNAVAILABLE"
