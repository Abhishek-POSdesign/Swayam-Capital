"""
Unit tests for Swayam Capital Rules Engine & TolerantComparator.

Verifies percentage-based evaluations, tolerance-band behavior at edge cases,
and dynamic rupee cap calculations.
"""

import pytest
from swayam.rules_engine import TolerantComparator, compute_rupee_cap


def test_tolerant_comparator_initializes_with_valid_tolerance() -> None:
    comp = TolerantComparator(tolerance_pct=0.02)
    assert comp.tolerance_pct == 0.02


def test_tolerant_comparator_rejects_negative_tolerance() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        TolerantComparator(tolerance_pct=-0.01)


def test_within_cap_passes_when_strictly_below_nominal_cap() -> None:
    comp = TolerantComparator(tolerance_pct=0.02)
    cap = 10000.0
    actual = 9950.0  # 99.5% of cap
    assert comp.within_cap(actual, cap) is True


def test_within_cap_passes_when_at_exact_nominal_cap() -> None:
    comp = TolerantComparator(tolerance_pct=0.02)
    cap = 10000.0
    assert comp.within_cap(10000.0, cap) is True


def test_within_cap_passes_when_within_tolerance_band() -> None:
    comp = TolerantComparator(tolerance_pct=0.02)
    cap = 10000.0
    # 101.5% of cap is within the 2% tolerance (cap * 1.02 = 10200.0)
    actual = 10150.0
    assert comp.within_cap(actual, cap) is True


def test_within_cap_passes_at_exact_tolerance_boundary() -> None:
    comp = TolerantComparator(tolerance_pct=0.02)
    cap = 10000.0
    actual = 10200.0  # Exactly 102% of cap
    assert comp.within_cap(actual, cap) is True


def test_within_cap_fails_when_exceeding_tolerance_band() -> None:
    comp = TolerantComparator(tolerance_pct=0.02)
    cap = 10000.0
    actual = 10500.0  # 105% of cap (fails)
    assert comp.within_cap(actual, cap) is False


def test_meets_floor_passes_when_strictly_above_nominal_floor() -> None:
    comp = TolerantComparator(tolerance_pct=0.02)
    floor = 2.0  # 1:2 R:R
    actual = 2.5  # 1:2.5 R:R
    assert comp.meets_floor(actual, floor) is True


def test_meets_floor_passes_when_within_tolerance_band() -> None:
    comp = TolerantComparator(tolerance_pct=0.02)
    floor = 2.0  # 1:2 R:R
    # With 2% tolerance, minimum acceptable floor is 2.0 * 0.98 = 1.96
    actual = 1.98
    assert comp.meets_floor(actual, floor) is True


def test_meets_floor_fails_when_dropping_below_tolerance_band() -> None:
    comp = TolerantComparator(tolerance_pct=0.02)
    floor = 2.0
    actual = 1.90  # 1.90 < 1.96 (fails)
    assert comp.meets_floor(actual, floor) is False


def test_compute_rupee_cap_calculates_correct_limits() -> None:
    margin_base = 850000.0
    per_trade_cap = compute_rupee_cap(0.01, margin_base)  # 1%
    daily_cap = compute_rupee_cap(0.02, margin_base)       # 2%
    weekly_cap = compute_rupee_cap(0.04, margin_base)      # 4%
    blast_radius = compute_rupee_cap(0.03, margin_base)    # 3%

    assert per_trade_cap == 8500.0
    assert daily_cap == 17000.0
    assert weekly_cap == 34000.0
    assert blast_radius == 25500.0
