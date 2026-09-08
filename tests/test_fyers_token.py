"""
The FYERS token is read at request time, not at container start.

The fault this guards against: Cloud Run resolves a `secretKeyRef` of
`latest` ONCE when the container starts, so a token refreshed at 08:30 never
reached a container started the night before, and the site showed no prices
all afternoon. The recorder had the same fault and failed every minute.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from swayam.services import fyers_token


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    fyers_token.clear_cache()
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("FUNCTION_TARGET", raising=False)
    monkeypatch.delenv("SWAYAM_TOKEN_FROM_SECRET_MANAGER", raising=False)
    yield
    fyers_token.clear_cache()


def _secret_client(value: str) -> MagicMock:
    client = MagicMock()
    client.access_secret_version.return_value = SimpleNamespace(
        payload=SimpleNamespace(data=value.encode("utf-8"))
    )
    return client


def test_local_development_uses_the_environment_variable_and_never_secret_manager(monkeypatch):
    monkeypatch.setenv("FYERS_ACCESS_TOKEN", "env-token")
    with patch.object(fyers_token, "_read_secret_manager", side_effect=AssertionError("must not be called")):
        assert fyers_token.get_access_token() == "env-token"


def test_on_cloud_run_the_latest_secret_wins_over_the_stale_env_value(monkeypatch):
    monkeypatch.setenv("K_SERVICE", "swayam-dashboard")
    monkeypatch.setenv("FYERS_ACCESS_TOKEN", "token-the-container-started-with")
    with patch.object(fyers_token, "_read_secret_manager", return_value="token-refreshed-this-morning") as read:
        assert fyers_token.get_access_token() == "token-refreshed-this-morning"
        read.assert_called_once_with("swayam-capital")


def test_secret_manager_is_read_at_most_once_a_minute(monkeypatch):
    monkeypatch.setenv("K_SERVICE", "swayam-dashboard")
    with patch.object(fyers_token, "_read_secret_manager", return_value="t1") as read:
        for _ in range(20):
            assert fyers_token.get_access_token() == "t1"
        assert read.call_count == 1
        # A forced read goes back to Secret Manager.
        read.return_value = "t2"
        assert fyers_token.get_access_token(force=True) == "t2"
        assert read.call_count == 2


def test_secret_manager_failure_falls_back_to_the_env_token_and_is_reported(monkeypatch):
    monkeypatch.setenv("K_SERVICE", "swayam-dashboard")
    monkeypatch.setenv("FYERS_ACCESS_TOKEN", "possibly-stale")
    with patch.object(fyers_token, "_read_secret_manager", side_effect=RuntimeError("403 permission denied")):
        assert fyers_token.get_access_token() == "possibly-stale"
    assert "403" in (fyers_token.last_error() or "")


def test_no_token_anywhere_is_an_empty_string_never_an_invented_one(monkeypatch):
    monkeypatch.setenv("K_SERVICE", "swayam-dashboard")
    monkeypatch.delenv("FYERS_ACCESS_TOKEN", raising=False)
    with patch.object(fyers_token, "_read_secret_manager", side_effect=RuntimeError("unreachable")):
        assert fyers_token.get_access_token() == ""


def test_secret_manager_request_names_the_latest_version(monkeypatch):
    fake_module = SimpleNamespace(SecretManagerServiceClient=lambda: _secret_client("abc\n"))
    with patch.dict("sys.modules", {"google.cloud.secretmanager": fake_module, "google.cloud": SimpleNamespace(secretmanager=fake_module)}):
        assert fyers_token._read_secret_manager("swayam-capital") == "abc"


def test_fyers_client_rebuilds_its_model_when_the_token_changes(monkeypatch):
    """The wrapper must not keep using the model built with yesterday's token."""
    from swayam.fyers_client import FyersClient

    built = []

    class FakeModel:
        def __init__(self, client_id, token, is_async, log_path):
            built.append(token)

    monkeypatch.setattr("swayam.fyers_client.fyersModel.FyersModel", FakeModel)
    client = FyersClient(app_id="APP-100")
    with patch("swayam.fyers_client.get_access_token", return_value="morning"):
        client.model
        client.model
    with patch("swayam.fyers_client.get_access_token", return_value="afternoon"):
        client.model
    assert built == ["morning", "afternoon"]


def test_fyers_client_explicit_token_stays_fixed(monkeypatch):
    from swayam.fyers_client import FyersClient

    client = FyersClient(app_id="APP-100", access_token="explicit")
    with patch("swayam.fyers_client.get_access_token", return_value="resolved"):
        assert client.access_token == "explicit"


def test_recorder_prefers_secret_manager_on_google_cloud(monkeypatch):
    """The recorder used to read the env var first, which never refreshed."""
    import importlib
    import sys
    from pathlib import Path

    recorder_dir = Path(__file__).resolve().parent.parent / "cloud" / "recorder"
    sys.path.insert(0, str(recorder_dir))
    try:
        config = importlib.import_module("config")
        importlib.reload(config)
        monkeypatch.setenv("K_SERVICE", "swayam-recorder")
        monkeypatch.setenv("FYERS_ACCESS_TOKEN", "stale-from-container-start")
        with patch.object(config, "_read_secret_manager", return_value="fresh-from-secret-manager") as read:
            assert config.get_fyers_access_token(force=True) == "fresh-from-secret-manager"
            assert config.get_fyers_access_token() == "fresh-from-secret-manager"
            assert read.call_count == 1  # cached for a minute
        with patch.object(config, "_read_secret_manager", side_effect=RuntimeError("down")):
            assert config.get_fyers_access_token(force=True) == "stale-from-container-start"
        monkeypatch.delenv("K_SERVICE")
        with patch.object(config, "_read_secret_manager", side_effect=AssertionError("not locally")):
            assert config.get_fyers_access_token(force=True) == "stale-from-container-start"
    finally:
        sys.path.remove(str(recorder_dir))
