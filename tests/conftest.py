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
