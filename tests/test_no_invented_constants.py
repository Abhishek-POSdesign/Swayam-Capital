"""
The eight invented constants, one test each, plus the two feeds that replace
"no wired source" with a real FYERS quote.

Round 2 brief, section 2.6. Each constant used to render on his screen as if
it were measured. Every one is None now, and the page says "unavailable".

| where                       | was    | now  |
|-----------------------------|--------|------|
| put-call ratio, no call OI  | 1.0    | None |
| ATR, no true ranges         | 150.0  | None |
| distance from 20-DMA, no ATR| 0.0    | None |
| realised vol, < 5 returns   | 12.0   | None |
| range position, flat range  | 50.0   | None |
| rollover in the window      | 68.5   | None |
| VIX current, no rows        | 0.0    | 503  |
| VIX percentile, no rows     | 50.0   | 503  |
"""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from swayam.api.main import app
from swayam.services.nifty_snapshot import (
    compute_breadth,
    compute_pcr_and_walls,
    compute_technical_metrics,
    front_month_futures_symbol,
    get_nifty_snapshot_data,
    load_nifty50_constituents,
)


def _candles(closes, spread=20.0):
    return [[i * 86400, c, c + spread, c - spread, c, 1000] for i, c in enumerate(closes)]


# --- 1. put-call ratio -------------------------------------------------------

def test_pcr_is_none_when_there_is_no_call_open_interest():
    stats = compute_pcr_and_walls([{"strike_price": 24800, "call_oi": 0, "put_oi": 5000}])
    assert stats["pcr"] is None


def test_pcr_is_none_for_an_empty_chain():
    assert compute_pcr_and_walls([])["pcr"] is None
    assert compute_pcr_and_walls([])["max_call_oi_strike"] is None


# --- 2, 3, 4, 5: the technical metrics ------------------------------------------

def test_every_technical_metric_is_none_when_the_series_is_too_short():
    m = compute_technical_metrics(_candles([100, 101, 102, 103]), 103.0)
    for key in ("atr_20", "distance_20_dma_atr", "realized_vol_20", "spot_position_pct_20d", "sentiment"):
        assert m[key] is None, key


def test_realised_vol_is_none_with_fewer_than_five_returns_and_measured_with_more():
    five = compute_technical_metrics(_candles([100, 101, 102, 101, 103]), 103.0)
    assert five["realized_vol_20"] is None  # four returns
    assert five["atr_20"] is not None       # but the ATR is a real measurement here

    six = compute_technical_metrics(_candles([100, 101, 102, 101, 103, 102]), 102.0)
    assert six["realized_vol_20"] is not None
    assert six["realized_vol_20"] != 12.0


def test_range_position_and_dma_distance_are_none_when_the_range_is_flat():
    m = compute_technical_metrics(_candles([100.0] * 25, spread=0.0), 100.0)
    assert m["atr_20"] == 0.0                 # measured: the bars never moved
    assert m["distance_20_dma_atr"] is None   # cannot divide by a zero ATR
    assert m["spot_position_pct_20d"] is None # a flat range has no inside
    assert m["sentiment"] is None


def test_metrics_are_real_numbers_on_a_normal_series():
    closes = [24000 + i * 20 for i in range(30)]
    m = compute_technical_metrics(_candles(closes), 24600.0)
    assert m["atr_20"] not in (None, 150.0)
    assert m["distance_20_dma_atr"] is not None
    assert m["realized_vol_20"] not in (None, 12.0)
    assert m["spot_position_pct_20d"] not in (None, 50.0)
    assert m["sentiment"] in ("Bullish", "Neutral", "Bearish")


# --- 6. rollover ------------------------------------------------------------------

def test_rollover_is_none_even_inside_the_rollover_window():
    mock_db = MagicMock()
    mock_db.client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
    meta = {
        "weekly_expiry": "2026-09-29", "monthly_expiry": "2026-09-29",
        "weekly_dte": {"formatted": "x"}, "monthly_dte": {"formatted": "x"},
        "is_rollover_window": True, "upcoming_expiries": ["2026-09-29"],
    }
    with (
        patch("swayam.services.nifty_snapshot.get_expiry_metadata", return_value=meta),
        patch("swayam.services.nifty_snapshot.fetch_live_quotes", return_value={}),
        patch("swayam.services.nifty_snapshot.fyers_client") as fy,
    ):
        fy.get_historical_candles.side_effect = RuntimeError("offline")
        fy.get_option_chain.side_effect = RuntimeError("offline")
        snap = get_nifty_snapshot_data(is_refresh=True, db=mock_db)
    assert snap["fno_pane"]["is_rollover_window"] is True
    assert snap["fno_pane"]["rollover_pct"] is None
    assert snap["fno_pane"]["rollover_freshness"] == "UNAVAILABLE"
    # And with FYERS offline, nothing else invents a number either.
    cash = snap["cash_pane"]
    assert cash["spot"] is None
    assert cash["atr_20"] is None
    assert cash["realized_vol_20"] is None
    assert cash["advances"] is None and cash["declines"] is None
    assert cash["futures_volume"] is None
    assert snap["fno_pane"]["weekly_pcr"] is None


# --- 7, 8. India VIX -----------------------------------------------------------------

def test_vix_endpoint_returns_the_real_last_close_and_a_real_percentile(mocker):
    mock_table = mocker.MagicMock()
    rows = [{"date": f"2026-08-{i:02d}", "vix_close": 10.0 + i * 0.25} for i in range(1, 26)]
    mock_table.select.return_value.gte.return_value.order.return_value.execute.return_value.data = rows
    mocker.patch("swayam.api.routes.market.db.client.table", return_value=mock_table)
    from swayam.api.routes.market import _vix_cache
    _vix_cache["data"] = None

    data = TestClient(app).get("/api/market/vix/history?days=60").json()
    assert data["current"] == 16.25          # the last row, not 0.0
    assert data["percentile"] == 96.0        # 24 of 25 below it, not 50.0


def test_vix_source_has_no_zero_or_fifty_fallback_left():
    import inspect
    from swayam.api.routes import market

    src = inspect.getsource(market.get_vix_history)
    assert "else 0.0" not in src
    assert "else 50.0" not in src


# --- breadth and futures volume, actually fetched ------------------------------------

def test_constituent_list_carries_fifty_symbols_and_a_date():
    c = load_nifty50_constituents()
    assert c["error"] is None
    assert len(c["symbols"]) == 50
    assert c["as_of"] is not None
    assert all(s.startswith("NSE:") and s.endswith("-EQ") for s in c["symbols"])


def test_breadth_counts_add_up_and_a_missing_quote_is_not_counted():
    symbols = ["NSE:A-EQ", "NSE:B-EQ", "NSE:C-EQ", "NSE:D-EQ"]
    quotes = {
        "NSE:A-EQ": {"lp": 101.0, "prev_close_price": 100.0},   # up
        "NSE:B-EQ": {"lp": 99.0, "prev_close_price": 100.0},    # down
        "NSE:C-EQ": {"lp": 100.0, "prev_close_price": 100.0},   # unchanged
        # D: no quote at all
    }
    b = compute_breadth(quotes, symbols)
    assert (b["advances"], b["declines"], b["unchanged"]) == (1, 1, 1)
    assert b["quoted"] == 3 and b["total"] == 4


def test_breadth_is_unavailable_when_nothing_was_quoted():
    b = compute_breadth({}, ["NSE:A-EQ", "NSE:B-EQ"])
    assert b["advances"] is None and b["declines"] is None
    assert b["quoted"] == 0


def test_front_month_futures_symbol_is_named_from_the_monthly_expiry():
    assert front_month_futures_symbol("2026-09-29") == "NSE:NIFTY26SEPFUT"
    assert front_month_futures_symbol("2026-10-27") == "NSE:NIFTY26OCTFUT"
    assert front_month_futures_symbol(None) is None


def test_snapshot_carries_breadth_and_futures_volume_from_real_quotes():
    mock_db = MagicMock()
    mock_db.client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
    meta = {
        "weekly_expiry": "2026-09-15", "monthly_expiry": "2026-09-29",
        "weekly_dte": {"formatted": "x"}, "monthly_dte": {"formatted": "x"},
        "is_rollover_window": False, "upcoming_expiries": ["2026-09-15", "2026-09-29"],
    }
    constituents = load_nifty50_constituents()["symbols"]

    def quotes(symbols):
        out = {}
        for i, s in enumerate(symbols):
            if s == "NSE:NIFTY26SEPFUT":
                out[s] = {"lp": 24900.0, "volume": 1234567}
            elif s in constituents:
                out[s] = {"lp": 100.0 + (1 if i % 2 == 0 else -1), "prev_close_price": 100.0}
        return out

    with (
        patch("swayam.services.nifty_snapshot.get_expiry_metadata", return_value=meta),
        patch("swayam.services.nifty_snapshot.fetch_live_quotes", side_effect=quotes),
        patch("swayam.services.nifty_snapshot.fyers_client") as fy,
    ):
        fy.get_historical_candles.side_effect = RuntimeError("offline")
        fy.get_option_chain.side_effect = RuntimeError("offline")
        snap = get_nifty_snapshot_data(is_refresh=True, db=mock_db)

    cash = snap["cash_pane"]
    assert cash["advances"] + cash["declines"] + cash["unchanged"] == 50
    assert cash["breadth_quoted"] == 50 and cash["breadth_total"] == 50
    assert cash["breadth_freshness"] == "LIVE"
    assert cash["breadth_as_of"] is not None
    assert cash["futures_symbol"] == "NSE:NIFTY26SEPFUT"
    assert cash["futures_volume"] == 1234567
    assert cash["futures_volume_freshness"] == "LIVE"


# --- the put-call ratio and max pain against FYERS' real row shape -------------------

FYERS_ROWS = [
    {"symbol": "NSE:NIFTY50-INDEX", "option_type": "", "strike_price": -1, "ltp": 23635.1, "oi": None},
    {"symbol": "NSE:NIFTY2690823500PE", "option_type": "PE", "strike_price": 23500, "ltp": 0.05, "oi": 9634625},
    {"symbol": "NSE:NIFTY2690823500CE", "option_type": "CE", "strike_price": 23500, "ltp": 134.8, "oi": 1313715},
    {"symbol": "NSE:NIFTY2690823550CE", "option_type": "CE", "strike_price": 23550, "ltp": 84.9, "oi": 1959685},
    {"symbol": "NSE:NIFTY2690823550PE", "option_type": "PE", "strike_price": 23550, "ltp": 0.05, "oi": 10632570},
    {"symbol": "NSE:NIFTY2690823600CE", "option_type": "CE", "strike_price": 23600, "ltp": 40.1, "oi": 4000000},
    {"symbol": "NSE:NIFTY2690823600PE", "option_type": "PE", "strike_price": 23600, "ltp": 2.0, "oi": 3000000},
]


def test_pcr_is_measured_from_fyers_per_contract_rows():
    """These rows are the real shape FYERS returned on 2026-09-08. The old code read
    call_oi/put_oi keys that do not exist, so every OI was zero and the PCR 1.0."""
    stats = compute_pcr_and_walls(FYERS_ROWS)
    total_call = 1313715 + 1959685 + 4000000
    total_put = 9634625 + 10632570 + 3000000
    assert stats["total_call_oi"] == total_call
    assert stats["total_put_oi"] == total_put
    assert stats["pcr"] == round(total_put / total_call, 2)
    assert stats["pcr"] != 1.0
    assert stats["max_call_oi_strike"] == 23600
    assert stats["max_put_oi_strike"] == 23550


def test_max_pain_is_measured_from_fyers_rows_and_none_when_there_is_no_open_interest():
    from swayam.services.nifty_snapshot import calculate_max_pain

    assert calculate_max_pain(FYERS_ROWS) in (23500.0, 23550.0, 23600.0)
    # Zero OI everywhere used to return the lowest strike as "max pain".
    zero = [dict(r, oi=0) for r in FYERS_ROWS]
    assert calculate_max_pain(zero) is None
    assert calculate_max_pain([]) is None
