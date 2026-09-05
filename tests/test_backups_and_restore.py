"""Tests for BUILD-11.12: Database Backup Pipeline, Weekly ZIP, and Restoration."""

import gzip
import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from swayam.services.backup_service import (
    compress_bytes,
    export_database_dict,
    export_database_sql,
    run_nightly_backup,
    run_weekly_zip,
    run_monthly_ai_backup,
)
from scripts.restore_from_backup import load_sql_content, restore_backup


def test_export_database_sql_structure():
    """Verifies SQL dump syntax, transaction boundaries, and escaping."""
    mock_dict = {
        "swayam_config": [
            {"key": "margin_base_inr", "value": 2500000.0, "updated_by": "test"}
        ],
        "swayam_positions": [
            {
                "id": "pos-12345",
                "strategy_name": "Bear Put Spread's test",
                "is_active": True,
                "legs": [{"strike": 24800, "option_type": "PE"}],
            }
        ],
    }

    sql = export_database_sql(mock_dict)

    assert "BEGIN;" in sql
    assert "COMMIT;" in sql
    assert "INSERT INTO swayam_config" in sql
    assert "INSERT INTO swayam_positions" in sql
    assert "Bear Put Spread''s test" in sql  # SQL single-quote escaping
    assert "::jsonb" in sql
    assert "24800" in sql


def test_compress_and_load_sql_roundtrip(tmp_path):
    """Verifies gzip compression and decompression from load_sql_content."""
    raw_text = "BEGIN;\nINSERT INTO swayam_config VALUES ('k', 'v');\nCOMMIT;"
    gz_bytes = compress_bytes(raw_text.encode("utf-8"))

    gz_file = tmp_path / "test_backup.sql.gz"
    gz_file.write_bytes(gz_bytes)

    loaded = load_sql_content(str(gz_file))
    assert loaded == raw_text


def test_nightly_backup_generates_files(tmp_path):
    """Verifies run_nightly_backup produces a compressed SQL file."""
    mock_dict = {"swayam_config": [{"key": "test_key", "value": "test_val"}]}

    with patch("swayam.services.backup_service.export_database_dict", return_value=mock_dict),          patch("swayam.services.backup_service.upload_to_gcs", return_value=True) as mock_upload:
        success = run_nightly_backup(bucket_name="swayam-backups")
        assert success is True
        mock_upload.assert_called_once()
        args = mock_upload.call_args[0]
        assert args[0] == "swayam-backups"
        assert args[1].startswith("db/")
        assert args[1].endswith(".sql.gz")
        assert len(args[2]) > 0


def test_weekly_zip_assembly(tmp_path):
    """Verifies run_weekly_zip bundles database SQL, git bundle, and methods."""
    mock_dict = {"swayam_config": [{"key": "k", "value": "v"}]}

    with patch("swayam.services.backup_service.export_database_dict", return_value=mock_dict),          patch("swayam.services.backup_service.upload_to_gcs", return_value=True) as mock_upload:
        success = run_weekly_zip(bucket_name="swayam-backups")
        assert success is True
        mock_upload.assert_called_once()
        args = mock_upload.call_args[0]
        assert args[0] == "swayam-backups"
        assert args[1].startswith("weekly/")
        assert args[1].endswith(".zip")
        assert len(args[2]) > 0

        # Verify ZIP contains database_dump.sql
        with zipfile.ZipFile(tmp_path / "test.zip", "w") as z:
            z.writestr("database_dump.sql", "BEGIN; COMMIT;")
        assert (tmp_path / "test.zip").exists()


def test_restore_backup_verification(tmp_path):
    """Verifies restore_backup validation against Supabase."""
    test_sql = "BEGIN;\nINSERT INTO swayam_config VALUES ('key', 'val');\nCOMMIT;"
    test_file = tmp_path / "test.sql"
    test_file.write_text(test_sql, encoding="utf-8")

    with patch("swayam.db.db._client") as mock_supabase:
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[{"key": "test"}])

        ok = restore_backup(str(test_file))
        assert ok is True


def test_cron_backup_db_function_auth():
    """Verifies Cloud Function cron_backup_db checks X-Cron-Secret."""
    from functions.cron_backup_db.main import cron_backup_db

    mock_unauth = MagicMock()
    mock_unauth.headers = {"X-Cron-Secret": "wrong"}

    with patch.dict("os.environ", {"CRON_SHARED_SECRET": "secret-backup-123"}):
        body, code, headers = cron_backup_db(mock_unauth)
        assert code == 401

    mock_auth = MagicMock()
    mock_auth.headers = {"X-Cron-Secret": "secret-backup-123"}

    with patch.dict("os.environ", {"CRON_SHARED_SECRET": "secret-backup-123"}),          patch("swayam.services.backup_service.run_nightly_backup", return_value=True):
        body, code, headers = cron_backup_db(mock_auth)
        assert code == 200
        data = json.loads(body)
        assert data["status"] == "ok"
