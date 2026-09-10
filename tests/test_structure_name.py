"""The structure's name comes from its open legs. A table, because it is pure.

His condor is stored as "Short Strangle" because a preset left that name
behind. docs/builds/BUILD_01_DESK_POSITION_AREA.md section 3.2 makes the name
a function of what he holds. This is that function's table.

Offline and deterministic: no database, no clock, no network.
"""

import pytest

from swayam.services.structure_name import is_open, name_from_legs, open_legs, resolve_name

NEAR = "2026-09-29"
FAR = "2026-10-27"


def leg(direction, strike, option_type, expiry=NEAR, **extra):
    row = {
        "direction": direction,
        "strike": strike,
        "option_type": option_type,
        "expiry_date": expiry,
    }
    row.update(extra)
    return row


# His real open condor, 7cd4d017, as its four legs are stored.
CONDOR = [
    leg("buy", 24200, "CE"),
    leg("buy", 22800, "PE"),
    leg("sell", 23800, "CE"),
    leg("sell", 23200, "PE"),
]


NAMES = [
    # one leg
    ([leg("buy", 23500, "CE")], "Long Call"),
    ([leg("buy", 23500, "PE")], "Long Put"),
    ([leg("sell", 23800, "CE")], "Short Call"),
    ([leg("sell", 23200, "PE")], "Short Put"),
    # verticals
    ([leg("buy", 23500, "CE"), leg("sell", 23800, "CE")], "Bull Call Spread"),
    ([leg("sell", 23500, "CE"), leg("buy", 23800, "CE")], "Bear Call Spread"),
    ([leg("buy", 23200, "PE"), leg("sell", 23500, "PE")], "Bull Put Spread"),
    ([leg("sell", 23200, "PE"), leg("buy", 23500, "PE")], "Bear Put Spread"),
    # straddles and strangles
    ([leg("buy", 23500, "CE"), leg("buy", 23500, "PE")], "Long Straddle"),
    ([leg("sell", 23500, "CE"), leg("sell", 23500, "PE")], "Short Straddle"),
    ([leg("buy", 23800, "CE"), leg("buy", 23200, "PE")], "Long Strangle"),
    ([leg("sell", 23800, "CE"), leg("sell", 23200, "PE")], "Short Strangle"),
    # four legs
    (CONDOR, "Iron Condor"),
    (
        [
            leg("buy", 24200, "CE"),
            leg("buy", 22800, "PE"),
            leg("sell", 23500, "CE"),
            leg("sell", 23500, "PE"),
        ],
        "Iron Butterfly",
    ),
    # calendars and diagonals: the far leg hedges, the near leg earns the theta
    ([leg("buy", 23500, "CE", FAR), leg("sell", 23500, "CE", NEAR)], "Call Calendar"),
    ([leg("buy", 23500, "PE", FAR), leg("sell", 23500, "PE", NEAR)], "Put Calendar"),
    ([leg("buy", 23600, "CE", FAR), leg("sell", 23500, "CE", NEAR)], "Diagonal"),
]


@pytest.mark.parametrize("legs,expected", NAMES, ids=[n for _, n in NAMES])
def test_named_structures(legs, expected):
    assert name_from_legs(legs) == expected


def test_the_condor_is_not_a_short_strangle():
    """The whole point. His four-leg condor must never come back as a strangle."""
    assert name_from_legs(CONDOR) == "Iron Condor"
    assert name_from_legs(CONDOR) != "Short Strangle"


def test_a_shape_it_cannot_name_says_so():
    three = [leg("buy", 23500, "CE"), leg("sell", 23800, "CE"), leg("sell", 23200, "PE")]
    assert name_from_legs(three) == "Custom, 3 legs"
    five = CONDOR + [leg("sell", 23400, "PE")]
    assert name_from_legs(five) == "Custom, 5 legs"


def test_wings_inside_the_body_is_not_a_condor():
    """Sold wings and bought body is a different trade, and is not named one."""
    inverted = [
        leg("sell", 24200, "CE"),
        leg("sell", 22800, "PE"),
        leg("buy", 23800, "CE"),
        leg("buy", 23200, "PE"),
    ]
    assert name_from_legs(inverted).startswith("Custom")


def test_two_calls_bought_is_not_a_spread():
    both_bought = [leg("buy", 23500, "CE"), leg("buy", 23800, "CE")]
    assert name_from_legs(both_bought) == "Custom, 2 legs"


# --------------------------------------------------------------- open legs


def test_a_leg_with_no_status_is_open():
    """Every leg on every row written before migration 022 has no status."""
    assert is_open({"direction": "buy"}) is True
    assert is_open({"direction": "buy", "status": "open"}) is True
    assert is_open({"direction": "buy", "status": "closed"}) is False


def test_only_open_legs_are_named():
    """One leg of the condor squared off, and it is no longer a condor.

    A trade is a campaign whose shape changes while it runs. The name has to
    follow what he still holds, not what he started with.
    """
    one_gone = [dict(CONDOR[0], status="closed")] + CONDOR[1:]
    assert len(open_legs(one_gone)) == 3
    assert name_from_legs(one_gone) == "Custom, 3 legs"

    # Take the other wing off too and what remains is the short strangle he
    # would actually be carrying.
    two_gone = [dict(CONDOR[0], status="closed"), dict(CONDOR[1], status="closed")] + CONDOR[2:]
    assert name_from_legs(two_gone) == "Short Strangle"


def test_every_leg_closed_says_so():
    assert name_from_legs([dict(l, status="closed") for l in CONDOR]) == "No open legs"


def test_no_legs_at_all():
    assert name_from_legs([]) == "No open legs"
    assert name_from_legs(None) == "No open legs"


# --------------------------------------------------------------- his name


def test_his_name_is_never_overwritten():
    assert resolve_name(CONDOR, name_source="his", current_name="September income") == "September income"


def test_the_structure_name_is_recomputed():
    assert resolve_name(CONDOR, name_source="structure", current_name="Short Strangle") == "Iron Condor"


def test_a_missing_name_source_behaves_like_structure():
    """Every row written before migration 022 has no name_source at all."""
    assert resolve_name(CONDOR, name_source=None, current_name="Short Strangle") == "Iron Condor"


def test_his_flag_with_no_name_falls_back_rather_than_blanking():
    assert resolve_name(CONDOR, name_source="his", current_name=None) == "Iron Condor"


# --------------------------------------------------------------- messy input


def test_junk_legs_are_ignored_not_guessed():
    messy = CONDOR + [{"direction": "buy"}, {"strike": 1, "option_type": "XX"}, "not a leg"]
    assert name_from_legs(messy) == "Iron Condor"


def test_alternative_field_spellings():
    """A leg from the desk says type and side; a stored leg says option_type."""
    desk_shaped = [
        {"side": "sell", "strike": 23800, "type": "CALL", "expiry": NEAR},
        {"side": "sell", "strike": 23200, "type": "PUT", "expiry": NEAR},
    ]
    assert name_from_legs(desk_shaped) == "Short Strangle"


def test_a_leg_with_no_expiry_does_not_invent_a_calendar():
    no_expiry = [
        {"direction": "buy", "strike": 23500, "option_type": "CE"},
        {"direction": "sell", "strike": 23500, "option_type": "CE", "expiry_date": NEAR},
    ]
    assert name_from_legs(no_expiry).startswith("Custom")
