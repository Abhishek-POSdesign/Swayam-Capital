"""
Pytest configuration for Swayam Capital test suite.
"""

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def default_mock_realized_vol(request):
    """Provides a default 14% realized volatility for tests unless test overrides it."""
    # Don't mock in test_realized_vol.py where compute_realized_vol is tested directly
    if "test_realized_vol" in request.node.nodeid:
        yield
        return

    with patch("swayam.api.routes.validation.compute_realized_vol", return_value=0.14):
        yield


@pytest.fixture(autouse=True)
def deterministic_capital(request):
    """Pins the account snapshot so tests never call the live broker.

    The risk gate reads real capital from FYERS. Left unmocked, every
    validation test would make a network call to Abhishek's live account, be
    slow, and change its answer whenever his balance moved. The figures below
    are his real ones as at 2026-09-07, so the numbers in these tests are the
    numbers he actually sees.

    Opt out with @pytest.mark.real_capital.
    """
    if request.node.get_closest_marker("real_capital"):
        yield
        return

    from datetime import date, datetime, timezone
    from swayam.services.capital import CapitalSnapshot

    snapshot = CapitalSnapshot(
        risk_capital_inr=971002.38,
        free_cash_inr=100000.0,
        collateral_inr=871002.38,
        cash_equivalent_pledged_inr=177480.46,
        cash_equivalent_as_of="2026-09-07",
        deployable_margin_ceiling_inr=554960.92,
        ceiling_unavailable_reason=None,
        reconciliation_note=None,
        taken_at=datetime(2026, 9, 7, 20, 0, tzinfo=timezone.utc),
        trading_day=date(2026, 9, 7),
    )
    with patch("swayam.api.routes.validation.get_capital", return_value=snapshot):
        yield


# ---------------------------------------------------------------------------
# The live-database write guard.
#
# Companion to `deterministic_capital` above. That fixture stops tests calling
# the live broker; this one stops them writing to the live record.
#
# There is no staging Supabase project (the free tier allows two and both are
# in use), so this guard is the only thing standing between a test run and
# Abhishek's real trading history. It has already been polluted twice.
#
# Default          reads pass through, writes raise WriteToLiveDatabaseError.
# @pytest.mark.fake_db   fully in-memory; writes accepted and recorded.
# @pytest.mark.live_db   unguarded. Nothing should use this.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def guard_live_database(request):
    """Refuses any test write to the live Supabase project."""
    from swayam.db import SupabaseDB
    from tests.db_guard import FakeClient, GuardedClient

    if request.node.get_closest_marker("live_db"):
        yield
        return

    real_client_property = SupabaseDB.client

    fake_marker = request.node.get_closest_marker("fake_db")
    if fake_marker:
        # `@pytest.mark.fake_db(seed={"swayam_config": [...]})` pre-loads rows the
        # code under test reads back. Every write path reads `margin_base_inr`,
        # so that row is seeded by default and a test may override it.
        seed = dict(fake_marker.kwargs.get("seed") or {})
        seed.setdefault(
            "swayam_config",
            [{"key": "margin_base_inr", "value": 850000.0}],
        )
        replacement = FakeClient(seed)
        request.node.fake_db = replacement
    else:
        replacement = GuardedClient(
            lambda: real_client_property.fget(SupabaseDB())
        )

    def guarded_client(self):
        # A test that injected its own mock (`monkeypatch.setattr(db, "_client", ...)`)
        # has already taken deliberate control of the database. Respect it. The
        # guard only stands in where a REAL client would otherwise be built,
        # which is the only path that can reach the live project.
        injected = getattr(self, "_client", None)
        if injected is not None:
            return injected
        return replacement

    with patch.object(SupabaseDB, "client", property(guarded_client)):
        yield replacement


@pytest.fixture
def fake_db(request):
    """The in-memory database for a test marked `@pytest.mark.fake_db`.

    Use it to assert on what would have been written:

        def test_one_position_only(fake_db):
            ...
            assert len(fake_db.inserted_into("swayam_positions")) == 1
    """
    from tests.db_guard import FakeClient

    replacement = getattr(request.node, "fake_db", None)
    if not isinstance(replacement, FakeClient):
        raise AssertionError(
            "The `fake_db` fixture requires the test to be marked "
            "@pytest.mark.fake_db, so the guard installs an in-memory database."
        )
    return replacement
