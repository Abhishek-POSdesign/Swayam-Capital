"""
Unit tests for Swayam Capital Smoketest health check tool.
"""

from unittest.mock import MagicMock, PropertyMock, patch
from swayam.smoketest import run_smoketest


def test_smoketest_runs_and_reports_status() -> None:
    # Mock external network clients so smoketest runs offline in test suite
    mock_supabase_client = MagicMock()
    mock_supabase_client.table.return_value.select.return_value.execute.return_value.data = [
        {"key": "margin_base_inr", "value": "850000"}
    ]

    with patch("swayam.fyers_client.fyers_client.get_profile", return_value={"name": "Abhishek", "fy_id": "YA38914"}), \
         patch("swayam.fyers_client.fyers_client.get_nifty_spot", return_value=24850.0), \
         patch("swayam.db.SupabaseDB.client", new_callable=PropertyMock, return_value=mock_supabase_client):
        result = run_smoketest()
        assert isinstance(result, bool)


def test_smoketest_includes_realized_vol_check(capsys) -> None:
    """Smoketest should output realized volatility line when data is present."""
    mock_supabase_client = MagicMock()
    mock_supabase_client.table.return_value.select.return_value.execute.return_value.data = [
        {"key": "margin_base_inr", "value": "850000"}
    ]

    with patch("swayam.fyers_client.fyers_client.get_profile", return_value={"name": "Abhishek", "fy_id": "YA38914"}), \
         patch("swayam.fyers_client.fyers_client.get_nifty_spot", return_value=24850.0), \
         patch("swayam.db.SupabaseDB.client", new_callable=PropertyMock, return_value=mock_supabase_client), \
         patch("swayam.options_math.realized_vol.compute_realized_vol", return_value=0.143):
        result = run_smoketest(skip_web=True)
        captured = capsys.readouterr().out
        assert "[OK] Realized Vol" in captured
        assert "14.3%" in captured

