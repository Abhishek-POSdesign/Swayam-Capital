"""The recorder must parse the shape FYERS actually returns, not an imagined one.

Why this file exists
--------------------
`tests/cloud/test_fyers_recorder.py` used to assert that the recorder correctly
read `call_ltp`, `put_oi`, `call_iv` and `call_pdoi` out of an option chain.
It passed. It passed every time for a week. FYERS has never returned any of
those keys, so what the test proved was that the recorder handled a response
nobody sends, while the response it does get produced twelve columns of zeros
and a wrong expiry date on every one of 10,332 rows.

So the fixture here is not written by hand. `tests/cloud/fixtures/
fyers_optionchain_2026-09-09.json` was captured from the live FYERS API on the
night of 9 September 2026 and trimmed only in the number of strikes. If FYERS
changes its shape, these tests break, which is the point.
"""

from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys

import pytest

RECORDER_DIR = Path(__file__).resolve().parent.parent.parent / "cloud" / "recorder"
if str(RECORDER_DIR) not in sys.path:
    sys.path.insert(0, str(RECORDER_DIR))

import fyers_recorder  # noqa: E402
from fyers_recorder import (  # noqa: E402
    build_rows,
    fetch_options_snapshot,
    parse_expiry_from_symbol,
    select_expiries,
    to_dataframe,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "fyers_optionchain_2026-09-09.json"
# The moment the fixture was captured, in UTC. Everything derived from it —
# the time to expiry, and therefore every Greek — is anchored to this.
CAPTURED_AT = datetime(2026, 9, 9, 18, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def captured():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class _StubFyers:
    """Replays the captured reply: the near chain, then the far one by epoch."""

    def __init__(self, captured, far_fails=False):
        self.captured = captured
        self.far_fails = far_fails
        self.calls = []

    def optionchain(self, data):
        self.calls.append(dict(data))
        if "timestamp" not in data:
            return self.captured["near"]
        if self.far_fails:
            return {"s": "error", "message": "request limit reached"}
        return self.captured["far"]


def test_the_underlying_row_is_where_the_nifty_level_comes_from(captured):
    rows = captured["near"]["data"]["optionsChain"]
    underlying = [r for r in rows if not r.get("option_type")]
    assert len(underlying) == 1, "FYERS sends exactly one underlying row in the chain"
    assert underlying[0]["strike_price"] == -1
    assert underlying[0]["ltp"] > 0
    # And the field the old code looked for is genuinely not there.
    assert "underlyingValue" not in captured["near"]["data"]
    assert fyers_recorder._spot_from_chain(rows) == underlying[0]["ltp"]


def test_the_keys_the_old_recorder_read_do_not_exist(captured):
    """Guards against anyone reintroducing the imagined shape."""
    absent = ("call_ltp", "put_ltp", "call_oi", "put_oi", "call_iv", "put_iv",
              "call_pdoi", "put_pdoi", "call_symbol", "put_symbol",
              "open", "high", "low", "prev_close")
    for row in captured["near"]["data"]["optionsChain"]:
        for key in absent:
            assert key not in row, f"FYERS now sends {key}; the recorder should use it"


def test_expiry_is_parsed_from_a_weekly_symbol():
    assert parse_expiry_from_symbol("NSE:NIFTY2691523300PE") == date(2026, 9, 15)
    assert parse_expiry_from_symbol("NIFTY2691523300PE") == date(2026, 9, 15)
    # October, November and December are single letters because the day follows.
    assert parse_expiry_from_symbol("NSE:NIFTY26O0623300CE") == date(2026, 10, 6)
    assert parse_expiry_from_symbol("NSE:NIFTY26N1024000CE") == date(2026, 11, 10)
    assert parse_expiry_from_symbol("NSE:NIFTY26D2924000PE") == date(2026, 12, 29)


def test_a_monthly_symbol_yields_no_date_rather_than_a_wrong_one():
    """It carries the month but not the day, so it must not guess one."""
    assert parse_expiry_from_symbol("NSE:NIFTY26SEP24000CE") is None
    assert parse_expiry_from_symbol("") is None
    assert parse_expiry_from_symbol("NSE:NIFTY50-INDEX") is None


def test_the_old_expiry_stub_would_now_fail():
    """The exact fault of 2026-09-09: every row stamped with today's date."""
    parsed = parse_expiry_from_symbol("NSE:NIFTY2691523300PE")
    assert parsed != date.today() or date.today() == date(2026, 9, 15)
    assert parsed == date(2026, 9, 15)


def test_two_expiries_are_selected_the_near_one_and_the_next_monthly(captured):
    chosen = select_expiries(captured["near"]["data"])
    assert [d for d, _ in chosen] == [date(2026, 9, 15), date(2026, 9, 29)]
    assert chosen[0][1] is None, "the near chain is already in hand; no second call for it"
    assert chosen[1][1] == captured["far_epoch"]


def test_a_snapshot_carries_real_numbers_and_blanks_never_zeros(captured):
    df = fetch_options_snapshot("token", client=_StubFyers(captured))

    assert not df.empty
    assert set(df["expiry_date"].unique()) == {date(2026, 9, 15), date(2026, 9, 29)}

    # Real, from FYERS.
    assert df["underlying_spot"].notna().all()
    assert (df["underlying_spot"] > 20000).all()
    assert df["close"].notna().all()
    assert df["bid"].notna().all()
    assert df["ask"].notna().all()
    assert df["open_interest"].notna().all()
    assert df["change_in_oi"].notna().all()
    assert df["change_in_oi"].abs().sum() > 0, "change in open interest is real, not a column of zeros"

    # Computed.
    assert df["iv"].notna().sum() > 0
    for greek in ("delta", "gamma", "theta", "vega"):
        assert df[greek].notna().sum() == df["iv"].notna().sum()

    # Genuinely unknown, and therefore blank. Not 0.0.
    for column in ("open", "high", "low", "settle_price", "turnover_inr"):
        assert df[column].isna().all(), f"{column} must be NULL, never zero"
        assert str(df[column].dtype) == "float64", f"{column} must keep a real column type"

    # No row anywhere carries a zero standing in for a missing value.
    for column in ("underlying_spot", "iv", "delta", "gamma", "vega"):
        assert not (df[column].dropna() == 0).any(), f"{column} has a zero masquerading as a value"


def test_the_greeks_are_the_ones_the_market_implies(captured):
    """A near-the-money call and put must look like a near-the-money call and put."""
    df = fetch_options_snapshot("token", client=_StubFyers(captured))
    near = df[df["expiry_date"] == date(2026, 9, 15)].dropna(subset=["iv"])
    spot = float(df["underlying_spot"].iloc[0])
    atm = near.iloc[(near["strike"] - spot).abs().argsort()[:2]]

    calls = atm[atm["option_type"] == "CE"]
    puts = atm[atm["option_type"] == "PE"]
    assert len(calls) and len(puts)

    assert 0.2 < float(calls["delta"].iloc[0]) < 0.8
    assert -0.8 < float(puts["delta"].iloc[0]) < -0.2
    assert (atm["gamma"] > 0).all()
    assert (atm["vega"] > 0).all()
    assert (atm["theta"] < 0).all(), "a long option loses value with time"
    # NIFTY at-the-money volatility sits in a believable band, not at 0.1% or 500%.
    assert (atm["iv"] > 0.02).all() and (atm["iv"] < 1.5).all()


def test_the_far_expiry_has_more_vega_and_slower_decay(captured):
    """The whole reason he trades calendars, and now visible in the archive."""
    df = fetch_options_snapshot("token", client=_StubFyers(captured))
    spot = float(df["underlying_spot"].iloc[0])
    solved = df.dropna(subset=["iv"])

    def atm_call(expiry):
        rows = solved[(solved["expiry_date"] == expiry) & (solved["option_type"] == "CE")]
        return rows.iloc[(rows["strike"] - spot).abs().argsort()[:1]].iloc[0]

    near = atm_call(date(2026, 9, 15))
    far = atm_call(date(2026, 9, 29))

    assert far["tte_years"] > near["tte_years"]
    assert far["vega"] > near["vega"], "the far leg carries the volatility exposure"
    assert far["theta"] > near["theta"], "the near leg is where the theta is earned"


def test_losing_the_far_expiry_still_records_the_near_one(captured):
    """Half a snapshot beats none, and the failure is not silent."""
    stub = _StubFyers(captured, far_fails=True)
    df = fetch_options_snapshot("token", client=stub)
    assert set(df["expiry_date"].unique()) == {date(2026, 9, 15)}
    assert not df.empty
    assert len(stub.calls) == 2, "it did try for the far expiry"


def test_a_chain_with_no_underlying_row_records_nothing(captured):
    """No NIFTY level means nothing can be valued, so nothing is written."""
    stripped = json.loads(json.dumps(captured, default=str))
    stripped["near"]["data"]["optionsChain"] = [
        r for r in captured["near"]["data"]["optionsChain"] if r.get("option_type")
    ]
    with pytest.raises(RuntimeError, match="no underlying row"):
        fetch_options_snapshot("token", client=_StubFyers(stripped))


def test_a_row_whose_symbol_contradicts_the_requested_expiry_is_dropped():
    """Better a missing row than a contract archived under the wrong expiry."""
    rows = [
        {"symbol": "NSE:NIFTY2691523400CE", "option_type": "CE", "strike_price": 23400,
         "ltp": 168.65, "bid": 167.25, "ask": 168.65, "oi": 1826955, "oich": 1484795,
         "prev_oi": 342160, "volume": 5529225},
        # Same chain, but this contract says it expires a week later.
        {"symbol": "NSE:NIFTY2692223400CE", "option_type": "CE", "strike_price": 23400,
         "ltp": 200.0, "bid": 199.0, "ask": 201.0, "oi": 100, "oich": 10,
         "prev_oi": 90, "volume": 500},
    ]
    built = build_rows(
        rows, expiry=date(2026, 9, 15), spot=23431.5,
        snapshot_utc=CAPTURED_AT, trade_date=date(2026, 9, 9),
    )
    assert [r["symbol"] for r in built] == ["NSE:NIFTY2691523400CE"]


def test_an_unpriced_strike_gets_no_volatility_and_no_greeks():
    """An illiquid strike with no trade is blank, not zero and not invented."""
    rows = [{"symbol": "NSE:NIFTY2691527000CE", "option_type": "CE", "strike_price": 27000,
             "ltp": 0, "bid": 0, "ask": 0.05, "oi": 0, "oich": 0, "prev_oi": 0, "volume": 0}]
    df = to_dataframe(build_rows(
        rows, expiry=date(2026, 9, 15), spot=23431.5,
        snapshot_utc=CAPTURED_AT, trade_date=date(2026, 9, 9),
    ))
    assert len(df) == 1
    row = df.iloc[0]
    assert row["close"] != row["close"]  # NaN: no traded price
    for column in ("iv", "delta", "gamma", "theta", "vega"):
        assert row[column] != row[column], f"{column} must be NULL when there is no price"
    # But the facts FYERS did send are kept, including a genuine zero.
    assert row["open_interest"] == 0
    assert row["ask"] == 0.05


def test_time_to_expiry_is_measured_to_the_close_not_to_midnight():
    """On expiry day the difference is the difference between sense and nonsense."""
    two_hours_before_close = datetime(2026, 9, 15, 8, 0, tzinfo=timezone.utc)  # 13:30 IST
    tte = fyers_recorder._tte_years(two_hours_before_close, date(2026, 9, 15))
    assert tte is not None
    hours = tte * 365 * 24
    assert 1.9 < hours < 2.1, f"expected about two hours, got {hours}"
    # After the close on expiry day there is no time left, and no Greeks.
    assert fyers_recorder._tte_years(
        datetime(2026, 9, 15, 11, 0, tzinfo=timezone.utc), date(2026, 9, 15)
    ) is None
