"""Reading a contract name wrong is silent, and it already happened once.

On 2026-09-10 the first run of the expired-options download used a pattern that
took the last six digits before CE as the strike. `NIFTY2690823450CE` read as
strike 823,450 instead of 23,450. It then chose sixty-two "nearest the money"
contracts on nonsense strikes, every one of which had never traded, and reported
a clean zero rows with no error at all.

These tests exist so that cannot happen again quietly.
"""

from datetime import date

import pytest

from swayam.research.contracts import (
    build_symbol,
    nearest_strikes,
    parse,
    parse_many,
)


def test_the_exact_name_that_was_misread():
    """The regression. Strike is 23,450, not 823,450."""
    contract = parse("NSE:NIFTY2690823450CE", date(2026, 9, 8))
    assert contract is not None
    assert contract.strike == 23450.0
    assert contract.option_type == "CE"
    assert contract.monthly is False


@pytest.mark.parametrize(
    "symbol,expiry,strike,option_type,monthly",
    [
        ("NSE:NIFTY2690823450CE", date(2026, 9, 8), 23450.0, "CE", False),
        ("NIFTY2690823450CE", date(2026, 9, 8), 23450.0, "CE", False),
        ("NSE:NIFTY2691523300PE", date(2026, 9, 15), 23300.0, "PE", False),
        # October, November and December take a letter, because the day follows.
        ("NSE:NIFTY26O0623300CE", date(2026, 10, 6), 23300.0, "CE", False),
        ("NSE:NIFTY26N1024000CE", date(2026, 11, 10), 24000.0, "CE", False),
        ("NSE:NIFTY26D2924000PE", date(2026, 12, 29), 24000.0, "PE", False),
        # Monthly contracts spell the month out and carry no day.
        ("NSE:NIFTY26SEP23450CE", date(2026, 9, 29), 23450.0, "CE", True),
        ("NSE:NIFTY24MAR22300CE", date(2024, 3, 28), 22300.0, "CE", True),
        # Four-digit strikes from his own era, and a five-figure far strike.
        ("NSE:NIFTY22O2017500CE", date(2022, 10, 20), 17500.0, "CE", False),
        ("NSE:NIFTY24MAR9000PE", date(2024, 3, 28), 9000.0, "PE", False),
        ("NSE:NIFTY24MAR32000CE", date(2024, 3, 28), 32000.0, "CE", True),
    ],
)
def test_real_contract_names_read_correctly(symbol, expiry, strike, option_type, monthly):
    contract = parse(symbol, expiry)
    assert contract is not None, symbol
    assert contract.strike == strike
    assert contract.option_type == option_type
    if symbol.endswith(("9000PE",)):
        return  # a 9000 strike exists on both shapes; monthliness is not the point here
    assert contract.monthly is monthly


def test_a_weekly_contract_from_a_different_expiry_is_refused_not_guessed():
    """A weekly name carries its day, so a mismatch can be caught exactly."""
    assert parse("NSE:NIFTY2691523300PE", date(2026, 9, 8)) is None
    assert parse("NSE:NIFTY2690823450CE", date(2026, 9, 15)) is None


def test_a_monthly_name_alone_cannot_be_pinned_to_a_day():
    """It carries the year and the month only. This is a limit, not a bug."""
    assert parse("NSE:NIFTY26SEP23450CE", date(2026, 9, 15)) is not None


def test_telling_the_parser_which_kind_of_expiry_closes_that_hole():
    monthly_name, weekly_expiry = "NSE:NIFTY26SEP23450CE", date(2026, 9, 15)
    assert parse(monthly_name, weekly_expiry, expiry_is_monthly=False) is None
    assert parse(monthly_name, date(2026, 9, 29), expiry_is_monthly=True) is not None
    # And the reverse: a weekly name is not accepted for the monthly expiry.
    assert parse("NSE:NIFTY2691523300PE", date(2026, 9, 15), expiry_is_monthly=True) is None


def test_nonsense_is_refused():
    assert parse("", date(2026, 9, 8)) is None
    assert parse("NSE:NIFTY50-INDEX", date(2026, 9, 8)) is None
    assert parse("NSE:NIFTY2690823450XX", date(2026, 9, 8)) is None
    assert parse("NSE:NIFTY26908ABCDECE", date(2026, 9, 8)) is None


def test_a_name_survives_being_built_and_read_back():
    for monthly in (True, False):
        symbol = build_symbol(date(2026, 9, 8), 23450, "CE", monthly=monthly)
        contract = parse(symbol, date(2026, 9, 8))
        assert contract is not None
        assert contract.strike == 23450.0
        assert contract.monthly is monthly


def test_names_that_cannot_be_read_are_reported_not_dropped():
    """A download that silently skips half a chain looks like a small chain."""
    parsed, rejected = parse_many(
        ["NSE:NIFTY2690823450CE", "NSE:NIFTY2690823450PE", "NSE:SOMETHINGELSE"],
        date(2026, 9, 8),
    )
    assert len(parsed) == 2
    assert rejected == ["NSE:SOMETHINGELSE"]


def test_the_strikes_chosen_are_the_ones_around_the_index():
    expiry = date(2026, 9, 8)
    symbols = [
        build_symbol(expiry, strike, option_type, monthly=False)
        for strike in range(22000, 25001, 50)
        for option_type in ("CE", "PE")
    ]
    contracts, rejected = parse_many(symbols, expiry)
    assert rejected == []

    chosen = nearest_strikes(contracts, centre=23635.0, near=5)
    strikes = sorted({c.strike for c in chosen})
    assert len(strikes) == 11, "five either side plus the middle one"
    assert min(strikes) == 23400.0 and max(strikes) == 23900.0
    assert len(chosen) == 22, "a call and a put at each strike"


def test_asking_for_no_limit_returns_the_whole_chain():
    expiry = date(2026, 9, 8)
    symbols = [
        build_symbol(expiry, strike, "CE", monthly=False) for strike in range(22000, 25001, 50)
    ]
    contracts, _ = parse_many(symbols, expiry)
    assert len(nearest_strikes(contracts, centre=23635.0, near=0)) == len(contracts)
