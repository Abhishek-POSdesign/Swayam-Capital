"""
Configuration module for Swayam Options Recorder Cloud Function.
"""

import os
import threading
import time
from typing import Optional

GCP_PROJECT_ID: str = os.getenv("GCP_PROJECT_ID", "swayam-capital")
GCS_OPTIONS_BUCKET: str = os.getenv("GCS_OPTIONS_BUCKET", "swayam-capital-options-data")

FYERS_CLIENT_ID: str = os.getenv("FYERS_CLIENT_ID", "YA38914")
FYERS_APP_ID: str = os.getenv("FYERS_APP_ID", "IWB0OQ1J1Y-200")
FYERS_ACCESS_TOKEN_SECRET_ID: str = os.getenv("FYERS_ACCESS_TOKEN_SECRET_ID", "fyers-access-token")

MARKET_OPEN_TIME: str = os.getenv("MARKET_OPEN_TIME", "09:15")
MARKET_CLOSE_TIME: str = os.getenv("MARKET_CLOSE_TIME", "15:30")
TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kolkata")
STRIKE_COUNT: int = int(os.getenv("STRIKE_COUNT", "20"))
UNDERLYING_SYMBOL: str = os.getenv("UNDERLYING_SYMBOL", "NSE:NIFTY50-INDEX")


TOKEN_CACHE_SECONDS = 60.0
_token_lock = threading.Lock()
_token_cache: dict[str, object] = {"token": None, "at": 0.0}


def running_on_google_cloud() -> bool:
    """Cloud Functions gen2 and Cloud Run both set K_SERVICE."""
    return bool(
        os.getenv("K_SERVICE")
        or os.getenv("FUNCTION_TARGET")
        or os.getenv("SWAYAM_TOKEN_FROM_SECRET_MANAGER") == "1"
    )


def _read_secret_manager() -> str:
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{GCP_PROJECT_ID}/secrets/{FYERS_ACCESS_TOKEN_SECRET_ID}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8").strip()


def get_fyers_access_token(force: bool = False) -> str:
    """The FYERS access token, read from Secret Manager at request time.

    Why the order matters: this function used to prefer the FYERS_ACCESS_TOKEN
    environment variable, which Cloud Functions resolves from the secret ONCE at
    container start. The recorder runs every minute, so its container never went
    cold, never re-read the secret, and after the morning token refresh it
    failed every call with "Please provide valid token" for the rest of the day.

    On Google Cloud: Secret Manager `latest`, cached for 60 seconds, so a
    refreshed token is in use within a minute with no redeploy. If Secret
    Manager cannot be reached, the environment value is used (real, possibly
    stale). Locally: the environment variable, as before.

    Raises:
        RuntimeError: If no token can be found anywhere.
    """
    env_token = os.getenv("FYERS_ACCESS_TOKEN", "").strip()

    if running_on_google_cloud():
        now = time.monotonic()
        with _token_lock:
            cached = _token_cache["token"]
            if cached and not force and now - float(_token_cache["at"]) < TOKEN_CACHE_SECONDS:
                return str(cached)
        try:
            secret_token = _read_secret_manager()
            if secret_token:
                with _token_lock:
                    _token_cache["token"] = secret_token
                    _token_cache["at"] = now
                return secret_token
            secret_error: Optional[str] = "the secret is empty"
        except Exception as e:  # noqa: BLE001 - fall through to the env token
            secret_error = str(e)
        if env_token:
            return env_token
        raise RuntimeError(
            f"Failed to retrieve FYERS access token from Secret Manager "
            f"({FYERS_ACCESS_TOKEN_SECRET_ID}): {secret_error}; and FYERS_ACCESS_TOKEN is not set."
        )

    if env_token:
        return env_token
    # Not on Google Cloud and no env token: try Secret Manager once as a courtesy.
    try:
        secret_token = _read_secret_manager()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            f"FYERS_ACCESS_TOKEN is not set and Secret Manager "
            f"({FYERS_ACCESS_TOKEN_SECRET_ID}) could not be read: {e}"
        ) from e
    if not secret_token:
        raise RuntimeError(f"Secret '{FYERS_ACCESS_TOKEN_SECRET_ID}' in Secret Manager is empty.")
    return secret_token
