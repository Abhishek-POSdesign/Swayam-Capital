"""The recorder and the terminal must price against the same interest rate.

Two rates would mean the archive and the screen quote different Greeks for the
same contract on the same afternoon, and there would be nothing on either to
say which was which.
"""

from pathlib import Path
import sys

RECORDER_DIR = Path(__file__).resolve().parent.parent.parent / "cloud" / "recorder"
if str(RECORDER_DIR) not in sys.path:
    sys.path.insert(0, str(RECORDER_DIR))

import config as recorder_config  # noqa: E402
from swayam.config import settings  # noqa: E402


def test_the_risk_free_rate_matches_the_terminals():
    assert recorder_config.RISK_FREE_RATE == settings.risk_free_rate, (
        "cloud/recorder/config.py and the terminal disagree about the risk-free rate. "
        "Set RISK_FREE_RATE on the deployed function, or update the recorder's default."
    )


def test_an_inline_comment_in_the_environment_does_not_stop_the_recorder_starting(monkeypatch):
    """His .env writes the rate with a comment after it. That must not be fatal."""
    monkeypatch.setenv("SWAYAM_TEST_RATE", "0.071   # RBI 91-day T-Bill rate")
    assert recorder_config._float_env("SWAYAM_TEST_RATE", 0.068) == 0.071


def test_an_unreadable_rate_falls_back_rather_than_crashing_on_import(monkeypatch):
    monkeypatch.setenv("SWAYAM_TEST_RATE", "not a number")
    assert recorder_config._float_env("SWAYAM_TEST_RATE", 0.068) == 0.068
    monkeypatch.delenv("SWAYAM_TEST_RATE", raising=False)
    assert recorder_config._float_env("SWAYAM_TEST_RATE", 0.068) == 0.068
