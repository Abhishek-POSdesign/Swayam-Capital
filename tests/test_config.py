"""
Unit tests for Swayam Capital Settings & Configuration.
"""

from swayam.config import Settings


def test_settings_initializes_with_defaults() -> None:
    s = Settings()
    assert s.risk_free_rate == 0.068
    assert s.default_tolerance_pct == 0.02
    assert s.ai_provider in ("vertex", "openrouter", "direct")


def test_validate_required_vars_detects_empty_fields() -> None:
    empty_settings = Settings(
        fyers_client_id="",
        fyers_app_id="",
        fyers_secret_key="",
        supabase_url="",
        supabase_anon_key="",
    )
    missing = empty_settings.validate_required_vars()
    assert "FYERS_CLIENT_ID" in missing
    assert "FYERS_APP_ID" in missing
    assert "SUPABASE_URL" in missing
