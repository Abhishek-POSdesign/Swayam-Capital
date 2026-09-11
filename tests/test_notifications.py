"""Unit tests for Swayam Capital Notification Pipeline (BUILD-11.8).

Verifies:
1. Event message formatting (clean, non-fluff, concise).
2. Telegram Bot sender resilience and error handling.
3. FCM Push sender resilience and error handling.
4. Unified best-effort event dispatcher (never raises, fans out independently).
5. Cloud Function cron handlers for readiness, overnight naked shorts, and EOD summary.
"""

from unittest.mock import MagicMock, patch
import pytest

from swayam.notifications.events import dispatch, format_event_message
from swayam.notifications.telegram import send_telegram_message
from swayam.notifications.push import send_push_notification
from functions.cron_notifications.main import handle_cron_job, cron_notifications_http


# =====================================================================
# 1. Event Message Formatting
# =====================================================================

def test_format_trade_opened():
    title, text = format_event_message(
        "trade_opened",
        {
            "strategy": "Bear Put Spread",
            "strikes": "BUY 24900 PE / SELL 24700 PE",
            "net_debit_inr": 4875.0,
            "mode": "paper",
            "session_id": "sess-123456",
        },
    )
    assert "📈 PAPER Trade Opened: Bear Put Spread" in title
    assert "Bear Put Spread opened · BUY 24900 PE / SELL 24700 PE" in text
    assert "Net Debit ₹4,875" in text
    assert "Session #sess-123456" in text


def test_format_trade_closed():
    title, text = format_event_message(
        "trade_closed",
        {
            "strategy": "Bear Put Spread",
            "pnl_inr": 2340.0,
            "close_reason": "target_hit",
            "position_id": "abcdef12-3456-7890-abcd-ef1234567890",
            "mode": "paper",
        },
    )
    assert "✅ PAPER Trade Closed: +₹2,340" in title
    assert "Bear Put Spread closed · P&L +₹2,340" in text
    assert "Reason: target_hit" in text
    assert "#abcdef12" in text


def test_format_rule_violation():
    title, text = format_event_message(
        "rule_violation",
        {
            "rule_id": "overnight_naked",
            "rule_name": "Overnight Naked Short Leg",
            "attempted_action": "Execute Naked Call",
            "reason": "Short leg without long protection violates Risk § 10a",
        },
    )
    assert "⚠ Rule Violation: Overnight Naked Short Leg" in title
    assert "⚠ RULE VIOLATION · Overnight Naked Short Leg · Blocked" in text
    assert "violates Risk § 10a" in text


def test_format_readiness_reminder():
    title, text = format_event_message("readiness_reminder", {})
    assert "☀ Readiness Ritual Pending" in title
    assert "08:45 IST · Readiness ritual pending" in text


def test_format_overnight_naked_warning():
    title, text = format_event_message(
        "overnight_naked_warning",
        {"position_id": "pos-88889999-1234"},
    )
    assert "⏰ 15:20 IST Risk Warning" in title
    assert "Position #pos-8888 has naked shorts" in text
    assert "before 15:30 IST" in text


def test_format_eod_summary():
    title, text = format_event_message(
        "eod_summary",
        {
            "opened_count": 2,
            "closed_count": 1,
            "unrealized_pnl_inr": 1250.0,
            "discipline_passed": True,
        },
    )
    assert "📊 15:30 IST EOD Summary: +₹1,250" in title
    assert "Today: 2 trade opened, 1 closed" in text
    assert "Unrealized P&L: +₹1,250" in text
    assert "Discipline: ✓" in text


# =====================================================================
# 2. Telegram Sender Resilience
# =====================================================================

def test_telegram_skipped_when_credentials_missing():
    # Neither token nor chat_id provided
    delivered = send_telegram_message("test", token="", chat_id="")
    assert delivered is False


def test_telegram_success_with_mock():
    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        delivered = send_telegram_message(
            "Hello Abhishek",
            token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="987654321",
        )
        assert delivered is True


def test_telegram_handles_network_error_gracefully():
    with patch("urllib.request.urlopen", side_effect=Exception("Connection timed out")):
        delivered = send_telegram_message(
            "Hello Abhishek",
            token="123456:test",
            chat_id="987654321",
        )
        # Never raises, returns False
        assert delivered is False


# =====================================================================
# 3. FCM Push Sender Resilience
# =====================================================================

def test_push_skipped_when_server_key_missing():
    delivered = send_push_notification("Title", "Body", server_key="", device_tokens=[])
    assert delivered is False


def test_push_skipped_when_no_devices_registered():
    delivered = send_push_notification("Title", "Body", server_key="test-key", device_tokens=[])
    assert delivered is False


def test_push_success_with_mock():
    mock_resp = MagicMock()
    mock_resp.getcode.return_value = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        delivered = send_push_notification(
            "Trade Executed",
            "Details here",
            server_key="test-fcm-server-key",
            device_tokens=["device-token-abc-123"],
        )
        assert delivered is True


def test_push_handles_network_error_gracefully():
    with patch("urllib.request.urlopen", side_effect=Exception("FCM endpoint unreachable")):
        delivered = send_push_notification(
            "Trade Executed",
            "Details here",
            server_key="test-fcm-server-key",
            device_tokens=["device-token-abc-123"],
        )
        # Never raises, returns False
        assert delivered is False


# =====================================================================
# 4. Best-Effort Dispatcher (CRITICAL INVARIANT)
# =====================================================================

def test_dispatch_fans_out_and_catches_exceptions():
    with patch("swayam.notifications.events.send_telegram_message", side_effect=RuntimeError("Telegram crash")),          patch("swayam.notifications.events.send_push_notification", return_value=True):
        
        # Telegram crashed, but dispatch must NOT raise and push still ran
        result = dispatch("readiness_reminder", {})
        assert result["event_type"] == "readiness_reminder"
        assert result["telegram"] is False
        assert result["push"] is True


def test_dispatch_push_crash_does_not_break_telegram():
    with patch("swayam.notifications.events.send_telegram_message", return_value=True),          patch("swayam.notifications.events.send_push_notification", side_effect=RuntimeError("Push crash")):
        
        result = dispatch("trade_opened", {"strategy": "Bull Call Spread"})
        assert result["telegram"] is True
        assert result["push"] is False


# =====================================================================
# 5. Cloud Function Cron Handlers
# =====================================================================

def test_handle_cron_readiness_pending(monkeypatch):
    from functions.cron_notifications import main as cron_main
    monkeypatch.setattr(cron_main, "check_readiness_pending", lambda: True)
    
    with patch("functions.cron_notifications.main.dispatch") as mock_dispatch:
        mock_dispatch.return_value = {"event_type": "readiness_reminder", "telegram": False}
        res = handle_cron_job("readiness_reminder")
        assert res["event_type"] == "readiness_reminder"
        mock_dispatch.assert_called_once_with("readiness_reminder", {})


def test_handle_cron_readiness_already_completed(monkeypatch):
    from functions.cron_notifications import main as cron_main
    monkeypatch.setattr(cron_main, "check_readiness_pending", lambda: False)
    
    res = handle_cron_job("readiness_reminder")
    assert res.get("status") == "skipped"
    assert res.get("reason") == "already_completed"


def test_handle_cron_overnight_naked_detected(monkeypatch):
    from functions.cron_notifications import main as cron_main
    monkeypatch.setattr(cron_main, "find_open_naked_shorts", lambda: ["pos-111", "pos-222"])
    
    with patch("functions.cron_notifications.main.dispatch") as mock_dispatch:
        mock_dispatch.return_value = {"event_type": "overnight_naked_warning"}
        res = handle_cron_job("overnight_naked_warning")
        assert res["event_type"] == "overnight_naked_warning"
        mock_dispatch.assert_called_once_with("overnight_naked_warning", {"position_id": "pos-111"})


def test_handle_cron_overnight_all_hedged(monkeypatch):
    from functions.cron_notifications import main as cron_main
    monkeypatch.setattr(cron_main, "find_open_naked_shorts", lambda: [])
    
    res = handle_cron_job("overnight_naked_warning")
    assert res.get("status") == "skipped"
    assert res.get("reason") == "all_hedged"


def test_handle_cron_eod_summary(monkeypatch):
    from functions.cron_notifications import main as cron_main
    metrics = {"opened_count": 3, "closed_count": 2, "unrealized_pnl_inr": 4500.0, "discipline_passed": True}
    monkeypatch.setattr(cron_main, "compute_eod_metrics", lambda: metrics)
    
    with patch("functions.cron_notifications.main.dispatch") as mock_dispatch:
        mock_dispatch.return_value = {"event_type": "eod_summary"}
        res = handle_cron_job("eod_summary")
        assert res["event_type"] == "eod_summary"
        mock_dispatch.assert_called_once_with("eod_summary", metrics)


def test_handle_cron_unknown_job():
    res = handle_cron_job("invalid_job_name")
    assert "error" in res


# =====================================================================
# 6. Endpoint Integration: Execution & Close Events
# =====================================================================

def test_execute_endpoint_dispatches_rule_violation_but_does_not_block():
    """A failing check is RECORDED, never enforced.

    ROUND 1b, FAULT 0c, from his live test of 11 September 2026: "Entry was
    blocked by a rule." The execute path raised 400 the moment any blocking
    check failed, and the overnight carry test was blocking, so with the plan
    chip on "carrying overnight" a naked leg could not be sent at all.

    His rule, settled 8 September: entry is NEVER blocked, including a naked or
    half-built structure, because converting a straddle into a condor has to
    pass through states no gate would allow. Only CARRYING is gated, at 15:20,
    by the naked-shorts check on what he actually holds.

    So the event is still dispatched -- the record must know he entered against
    a failing check -- and the trade is no longer refused for it. The send here
    gets as far as the fill, which is a different gate entirely.
    """
    from fastapi.testclient import TestClient
    from swayam.api.main import app

    client = TestClient(app)
    with patch("swayam.api.routes.execution.audit_strategy_rules") as mock_audit, \
         patch("swayam.api.routes.execution.dispatch") as mock_dispatch:
        # `verdict` is set on the mock itself now, not only inside model_dump.
        # The old code reached the dispatch through `passed`; the new code reads
        # the verdict of each check, which is the thing that actually failed.
        failing_check = MagicMock(
            verdict="FAIL",
            model_dump=lambda: {"rule": "blast_radius", "verdict": "FAIL", "note": "Exceeds 5%"},
        )
        mock_audit.return_value = MagicMock(passed=False, checks=[failing_check])

        payload = {
            "strategy_name": "Test Rogue",
            "underlying": "NIFTY",
            "legs": [{
                "strike": 25000,
                "option_type": "CE",
                "direction": "SELL",
                "quantity_lots": 10,
                "entry_premium": 100,
                "expiry_date": "2026-09-09",
            }],
            "current_spot": 24800,
            "mode": "paper",
        }
        resp = client.post("/api/execute", json=payload)
        # NOT 400. A rule does not stop an entry any more. Whatever answer the
        # fill stage gives, it is not "Strategy violates Method rules".
        assert "violates Method rules" not in resp.text
        mock_dispatch.assert_called_once()
        assert mock_dispatch.call_args[0][0] == "rule_violation"


def test_execute_endpoint_best_effort_dispatch_on_success():
    from fastapi.testclient import TestClient
    from swayam.api.main import app

    client = TestClient(app)
    with patch("swayam.api.routes.execution.audit_strategy_rules") as mock_audit, \
         patch("swayam.api.routes.execution.build_spread_from_request") as mock_spread, \
         patch("swayam.api.routes.execution.compute_payoff_curve") as mock_curve, \
         patch("swayam.api.routes.execution.compute_position_greeks") as mock_greeks, \
         patch("swayam.api.routes.execution.db") as mock_db, \
         patch("swayam.api.routes.execution.write_new_trade_journal") as mock_j, \
         patch("swayam.api.routes.execution.dispatch", side_effect=Exception("Dispatch exploded!")) as mock_dispatch:

        mock_audit.return_value = MagicMock(passed=True, checks=[], model_dump=lambda: {})
        # THREE VALUES, because that is what the real function returns.
        #
        # `build_spread_from_request` answers (Spread, Leg->IV, Leg->iv_available).
        # The third was added when the desk had to tell a measured volatility
        # from a substituted one, every real caller was updated, and this mock
        # was left behind returning two. The route unpacked three and raised
        # `ValueError: not enough values to unpack (expected 3, got 2)` before
        # it reached the dispatch this test is actually about.
        #
        # THE TEST WAS NEVER WRONG ABOUT THE APP. It has been reported as "the
        # one long-standing failure" for weeks, which is exactly how a real red
        # hides: everyone learns to skip that line.
        mock_spread.return_value = (MagicMock(), {}, {})
        mock_curve.return_value = MagicMock(
            max_loss_inr=5000, max_profit_inr=10000, rr_implied=2.0, net_debit_credit_inr=5000, breakevens=[24800]
        )
        mock_greeks.return_value = MagicMock(net_delta=0.1, net_gamma=0.01, net_theta_per_day=-10, net_vega=5)
        mock_db.get_margin_base_inr.return_value = 850000.0
        mock_db.client.table.return_value.insert.return_value.execute.return_value = MagicMock()
        mock_j.return_value = "Trade Journal/test.md"

        payload = {
            "strategy_name": "Bear Put Spread",
            "underlying": "NIFTY",
            "legs": [
                {"strike": 24900, "option_type": "PE", "direction": "BUY", "quantity_lots": 1, "entry_premium": 100, "expiry_date": "2026-09-09"},
                {"strike": 24700, "option_type": "PE", "direction": "SELL", "quantity_lots": 1, "entry_premium": 40, "expiry_date": "2026-09-09"},
            ],
            "current_spot": 24800,
            "mode": "paper",
        }
        resp = client.post("/api/execute", json=payload)
        # MUST succeed (200) despite dispatch failure
        assert resp.status_code == 200
        mock_dispatch.assert_called_once()
        assert mock_dispatch.call_args[0][0] == "trade_opened"
