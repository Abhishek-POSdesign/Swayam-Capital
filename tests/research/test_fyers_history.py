"""The history client must pace itself and never invent a candle.

It spends from the same FYERS request budget the live desk uses to quote his
legs. On 2026-09-08 an unthrottled caller produced 46 refusals in ten minutes
and blank prices on his screen. These tests hold that line.

No network. Every response here is a stub.
"""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from swayam.research.fyers_history import (
    MAX_DAYS_DAILY,
    MAX_DAYS_MINUTE,
    FyersHistory,
    FyersHistoryError,
    date_chunks,
    in_his_trading_window,
)

IST = ZoneInfo("Asia/Kolkata")


class _StubSession:
    """Replays a queue of FYERS replies and records what was asked for."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    def get(self, url, headers=None, params=None, timeout=None):
        self.requests.append({"url": url, "params": dict(params or {})})
        body = self.replies.pop(0) if self.replies else {"s": "ok", "candles": []}

        class _Response:
            status_code = 200

            def json(self_inner):
                return body

        return _Response()


def _client(replies):
    return FyersHistory(
        app_id="APP-100", access_token="tok", pause_seconds=0.0,
        session=_StubSession(replies),
    )


# ------------------------------------------------------------------ chunking

def test_a_span_is_split_into_pieces_fyers_will_accept():
    chunks = list(date_chunks(date(2018, 1, 1), date(2018, 12, 31), MAX_DAYS_MINUTE))
    assert chunks[0][0] == date(2018, 1, 1)
    assert chunks[-1][1] == date(2018, 12, 31)
    for start, end in chunks:
        assert (end - start).days < MAX_DAYS_MINUTE


def test_the_chunks_cover_the_span_with_no_gap_and_no_overlap():
    chunks = list(date_chunks(date(2020, 1, 1), date(2022, 6, 30), MAX_DAYS_DAILY))
    for earlier, later in zip(chunks, chunks[1:]):
        assert (later[0] - earlier[1]).days == 1


def test_a_single_day_is_one_chunk():
    assert list(date_chunks(date(2026, 9, 9), date(2026, 9, 9), 90)) == [
        (date(2026, 9, 9), date(2026, 9, 9))
    ]


# ------------------------------------------------------------- his window

@pytest.mark.parametrize(
    "when,expected",
    [
        (datetime(2026, 9, 9, 14, 0, tzinfo=IST), True),    # he is at the desk
        (datetime(2026, 9, 9, 13, 0, tzinfo=IST), True),
        (datetime(2026, 9, 9, 2, 0, tzinfo=IST), False),    # the middle of the night
        (datetime(2026, 9, 9, 20, 0, tzinfo=IST), False),   # after his day
        (datetime(2026, 9, 12, 14, 0, tzinfo=IST), False),  # Saturday
    ],
)
def test_bulk_downloads_know_when_he_might_be_trading(when, expected):
    assert in_his_trading_window(when) is expected


# ---------------------------------------------------------------- refusals

def test_no_data_is_an_empty_list_not_an_error():
    """FYERS says `no_data` for a span it holds nothing for. That is normal."""
    client = _client([{"s": "no_data"}])
    assert client.candles("NSE:NIFTY50-INDEX", "1", date(2017, 1, 1), date(2017, 3, 1)) == []


def test_a_refusal_on_volume_is_retried_after_standing_back(monkeypatch):
    slept = []
    monkeypatch.setattr("swayam.research.fyers_history.time.sleep", lambda s: slept.append(s))
    client = _client([
        {"s": "error", "message": "request limit reached"},
        {"s": "ok", "candles": [[1788752760, 600.0, 601.0, 599.0, 600.5, 455]]},
    ])
    candles = client.candles("NSE:NIFTY50-INDEX", "1", date(2026, 9, 5), date(2026, 9, 9))
    assert len(candles) == 1
    assert client.refusals == 1
    assert slept and slept[0] >= 5.0, "it must actually wait before asking again"


def test_a_dead_token_stops_immediately_and_says_what_to_do(monkeypatch):
    """Retrying a dead token is pointless and spends his budget for nothing."""
    monkeypatch.setattr("swayam.research.fyers_history.time.sleep", lambda s: None)
    client = _client([{"s": "error", "message": "Please provide valid token"}])
    with pytest.raises(FyersHistoryError) as caught:
        client.candles("NSE:NIFTY50-INDEX", "1", date(2026, 9, 5), date(2026, 9, 9))
    assert "Refresh-Token" in str(caught.value)
    assert "resumes where it stopped" in str(caught.value)
    assert client.calls == 1, "a dead token must not be retried"


def test_any_other_refusal_is_raised_with_what_fyers_said():
    client = _client([{"s": "error", "message": "Invalid input"}])
    with pytest.raises(FyersHistoryError, match="Invalid input"):
        client.candles("NSE:NIFTY50-INDEX", "1", date(2026, 1, 1), date(2026, 9, 9))


# ------------------------------------------------------ the expired endpoints

def test_expired_contracts_are_asked_for_on_the_separate_route():
    """The ordinary history route cannot see an expired contract. Proven live."""
    client = _client([{"s": "ok", "data": {"contracts": {"options": ["NSE:NIFTY24MAR22300CE"]}}}])
    contracts = client.expired_contracts("NSE:NIFTY50-INDEX", date(2024, 3, 28))
    assert contracts == ["NSE:NIFTY24MAR22300CE"]
    asked = client.session.requests[0]
    assert asked["url"].endswith("/history/fno/expired/underlying-symbols")
    assert asked["params"]["expiry_date"] == "2024-03-28"


def test_expiry_dates_come_back_split_into_options_and_futures():
    client = _client([{
        "s": "ok",
        "data": {"expiry_dates": {"options": ["2024-03-28"], "futures": ["2024-03-28"]}},
    }])
    listed = client.expired_expiry_dates("NSE:NIFTY50-INDEX", date(2024, 1, 1), date(2024, 3, 31))
    assert listed["options"] == ["2024-03-28"]


def test_an_expiry_fyers_holds_no_candles_for_is_empty_not_an_error():
    """Everything before February 2024 answers this way. Measured, not assumed."""
    client = _client([{"s": "no_data"}])
    assert client.expired_candles(
        "NSE:NIFTY22O2017500CE", "1", date(2022, 10, 17), date(2022, 10, 20)
    ) == []


def test_the_authorization_header_is_the_app_id_and_the_token():
    client = _client([{"s": "ok", "candles": []}])
    client.candles("NSE:NIFTY50-INDEX", "D", date(2026, 9, 1), date(2026, 9, 9))
    assert client.headers["Authorization"] == "APP-100:tok"
    assert client.headers["version"] == "3"
