"""
The FYERS access token, read at request time rather than at container start.

Why this exists
---------------
`FYERS_ACCESS_TOKEN` reaches Cloud Run as a `secretKeyRef` with key `latest`,
and Google resolves `latest` ONCE, when the container starts. His 08:30 token
refresh therefore never reached a container that started the night before, and
the site showed "Live NIFTY price unavailable" all afternoon with nothing
explaining why. The recorder had the same fault from the other direction: it
runs every minute, so its container never went cold and never re-read the
secret, and it failed every call with `Please provide valid token`.

What this does
--------------
On Google Cloud (Cloud Run sets `K_SERVICE`; Cloud Functions gen2 sets it too)
the `latest` version of the `fyers-access-token` secret is read from Secret
Manager on demand, with a 60-second in-process cache so a page full of
requests does not become a page full of Secret Manager calls. A refreshed
token is therefore live within a minute, with no restart and no redeploy.

Locally, `FYERS_ACCESS_TOKEN` from the environment is used exactly as before,
so nothing changes for local development. Set `SWAYAM_TOKEN_FROM_SECRET_MANAGER=1`
to force the Secret Manager path off Google Cloud, for example to test it.

If Secret Manager cannot be reached, the environment value is returned: it is
the token the container started with, real but possibly stale. Nothing here
ever fabricates a token, and an empty string is returned when there is none.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

SECRET_ID = os.getenv("FYERS_ACCESS_TOKEN_SECRET_ID", "fyers-access-token")
CACHE_SECONDS = 60.0

_lock = threading.Lock()
_cached_token: Optional[str] = None
_cached_at: float = 0.0
_last_error: Optional[str] = None
_last_error_logged_at: float = 0.0


def running_on_google_cloud() -> bool:
    """True on Cloud Run and Cloud Functions gen2, or when forced by env."""
    return bool(
        os.getenv("K_SERVICE")
        or os.getenv("FUNCTION_TARGET")
        or os.getenv("SWAYAM_TOKEN_FROM_SECRET_MANAGER") == "1"
    )


def _read_secret_manager(project_id: str) -> str:
    from google.cloud import secretmanager  # imported lazily: not needed locally

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{SECRET_ID}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("utf-8").strip()


def get_access_token(*, force: bool = False) -> str:
    """The current FYERS access token, or an empty string if there is none.

    Never raises. Never invents. On Google Cloud it is the `latest` secret
    version, cached for 60 seconds; elsewhere it is the environment variable.
    """
    global _cached_token, _cached_at, _last_error, _last_error_logged_at

    env_token = os.getenv("FYERS_ACCESS_TOKEN", "").strip()
    if not running_on_google_cloud():
        return env_token

    now = time.monotonic()
    with _lock:
        if _cached_token and not force and (now - _cached_at) < CACHE_SECONDS:
            return _cached_token

    project_id = os.getenv("GCP_PROJECT_ID", "swayam-capital")
    try:
        token = _read_secret_manager(project_id)
        if token:
            with _lock:
                _cached_token = token
                _cached_at = now
                _last_error = None
            return token
        _last_error = f"Secret {SECRET_ID} is empty"
    except Exception as exc:  # noqa: BLE001 - the fallback below is the point
        _last_error = str(exc)

    # Log the failure, but not on every one of the requests that hit it.
    if now - _last_error_logged_at > CACHE_SECONDS:
        _last_error_logged_at = now
        logger.warning(
            "Could not read the FYERS token from Secret Manager (%s); using the "
            "token the container started with, which may be stale.",
            _last_error,
        )

    if env_token:
        return env_token
    with _lock:
        return _cached_token or ""


def last_error() -> Optional[str]:
    """The most recent Secret Manager failure, for diagnostics. None when healthy."""
    return _last_error


def clear_cache() -> None:
    """Forget the cached token. Used by tests and by the token refresh script."""
    global _cached_token, _cached_at, _last_error
    with _lock:
        _cached_token = None
        _cached_at = 0.0
        _last_error = None
