"""Tests for BUILD-11.11: PWA Device Registration, Weekly Email Digest, and Cron Function."""

import json
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from swayam.api.main import app
from swayam.services.email_digest import compose_digest_html, send_weekly_digest


@pytest.fixture
def client():
    return TestClient(app)


def test_device_registration_endpoint(client):
    """Verifies POST /api/notifications/register-device registers device token."""
    payload = {
        "device_token": "fcm-token-test-12345",
        "browser_ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "platform": "windows",
    }
    with patch("swayam.db.db._client") as mock_supabase:
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_table.upsert.return_value = mock_table
        mock_table.execute.return_value = MagicMock(data=[payload])

        resp = client.post("/api/notifications/register-device", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "registered"
        assert data["device_token"] == "fcm-token-test-12345"

    # Test empty token validation
    empty_resp = client.post("/api/notifications/register-device", json={"device_token": ""})
    assert empty_resp.status_code == 400


def test_compose_digest_html_content_and_metrics():
    """Verifies HTML digest calculations, trade table formatting, lesson, and macro events."""
    sample_trades = [
        {
            "strategy_name": "Bear Put Spread 24800/24600",
            "pnl": 4250.0,
            "discipline_followed": True,
            "exit_time": "2026-09-02T15:15:00Z",
        },
        {
            "strategy_name": "Bull Call Spread 24900/25100",
            "pnl": -1500.0,
            "discipline_followed": True,
            "exit_time": "2026-09-04T14:30:00Z",
        },
    ]

    sample_lessons = [
        {
            "category": "Risk Management",
            "lesson_text": "Never widen the wing on an intraday gap against your structure.",
        }
    ]

    sample_macro_events = [
        {
            "event_name": "India CPI Inflation (YoY)",
            "event_date": "2026-09-10",
            "country": "IN",
            "impact_brief": "Key inflation marker for RBI rate path.",
        }
    ]

    html = compose_digest_html(
        trades=sample_trades,
        lessons=sample_lessons,
        macro_events=sample_macro_events,
        date_range_str="31 Aug – 06 Sep 2026",
    )

    # 1. Check title & date range
    assert "Swayam Capital" in html
    assert "31 Aug – 06 Sep 2026" in html

    # 2. Check net P&L and discipline rate
    # Net P&L = 4250 - 1500 = +2750.00
    assert "+₹2,750.00" in html
    # Discipline rate = 2/2 = 100%
    assert "100%" in html
    assert "2/2 rules respected" in html

    # 3. Check trade table rows
    assert "Bear Put Spread 24800/24600" in html
    assert "+₹4,250.00" in html
    assert "Bull Call Spread 24900/25100" in html
    assert "-₹1,500.00" in html

    # 4. Check lesson section
    assert "Risk Management" in html
    assert "Never widen the wing on an intraday gap" in html

    # 5. Check macro calendar
    assert "India CPI Inflation (YoY)" in html
    assert "Key inflation marker for RBI rate path." in html

    # 6. Check CTA link
    assert "https://swayam.abhisheksikka.com" in html


def test_send_weekly_digest_skipped_without_credentials():
    """Verifies best-effort safety: skips if GMAIL_SENDER_ADDRESS or GMAIL_APP_PASSWORD not configured."""
    result = send_weekly_digest(sender_email="", app_password="", trades=[], lessons=[], macro_events=[])
    assert result is False


def test_send_weekly_digest_smtp_dispatch():
    """Verifies SMTP_SSL connection and message dispatch when credentials are provided."""
    with patch("smtplib.SMTP_SSL") as mock_smtp_class:
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        success = send_weekly_digest(
            sender_email="abhisheksikka99.99@gmail.com",
            app_password="test-app-password-1234",
            recipient_email="abhisheksikka99.99@gmail.com",
            trades=[],
            lessons=[],
            macro_events=[],
        )

        assert success is True
        mock_server.login.assert_called_once_with("abhisheksikka99.99@gmail.com", "test-app-password-1234")
        mock_server.sendmail.assert_called_once()
        args = mock_server.sendmail.call_args[0]
        assert args[0] == "abhisheksikka99.99@gmail.com"
        assert args[1] == ["abhisheksikka99.99@gmail.com"]


def test_cron_email_digest_function_auth():
    """Verifies cron_email_digest Cloud Function verifies X-Cron-Secret header."""
    from functions.cron_email_digest.main import cron_email_digest

    mock_unauth_req = MagicMock()
    mock_unauth_req.headers = {"X-Cron-Secret": "wrong-secret"}

    with patch.dict("os.environ", {"CRON_SHARED_SECRET": "correct-secret-123"}):
        body, code, headers = cron_email_digest(mock_unauth_req)
        assert code == 401
        assert "Unauthorized" in body

    mock_auth_req = MagicMock()
    mock_auth_req.headers = {"X-Cron-Secret": "correct-secret-123"}

    with patch.dict("os.environ", {"CRON_SHARED_SECRET": "correct-secret-123"}), \
         patch("swayam.services.email_digest.send_weekly_digest", return_value=True):
        body, code, headers = cron_email_digest(mock_auth_req)
        assert code == 200
        data = json.loads(body)
        assert data["status"] == "ok"
        assert data["message"] == "Email digest sent"
