"""
Unit tests for Swayam Capital Supabase DB wrapper.
"""

import pytest
from swayam.db import DatabaseError, SupabaseDB


def test_get_margin_base_inr_raises_when_config_row_missing(mocker) -> None:
    """If the config table doesn't have margin_base_inr, DatabaseError must be raised."""
    db_instance = SupabaseDB(url="https://test.supabase.co", key="test_key")
    mocker.patch.object(db_instance, "get_config", return_value=None)

    with pytest.raises(DatabaseError, match="not found"):
        db_instance.get_margin_base_inr()


def test_get_margin_base_inr_raises_when_value_invalid(mocker) -> None:
    """If the config value is not a numeric value, DatabaseError must be raised."""
    db_instance = SupabaseDB(url="https://test.supabase.co", key="test_key")
    mocker.patch.object(db_instance, "get_config", return_value="invalid_float_string")

    with pytest.raises(DatabaseError, match="not a valid float"):
        db_instance.get_margin_base_inr()


def test_get_margin_base_inr_returns_valid_float(mocker) -> None:
    """If the config table has a valid numeric value, return it as float."""
    db_instance = SupabaseDB(url="https://test.supabase.co", key="test_key")
    mocker.patch.object(db_instance, "get_config", return_value="850000")

    result = db_instance.get_margin_base_inr()
    assert result == 850000.0
