"""
Configuration module for Swayam Options Recorder Cloud Function.
"""

import os
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


def get_fyers_access_token() -> str:
    """Retrieves FYERS access token from environment variable or GCP Secret Manager.

    Raises:
        RuntimeError: If token cannot be retrieved or is empty.
    """
    token = os.getenv("FYERS_ACCESS_TOKEN", "").strip()
    if token:
        return token

    # Fallback to GCP Secret Manager
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{GCP_PROJECT_ID}/secrets/{FYERS_ACCESS_TOKEN_SECRET_ID}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        secret_token = response.payload.data.decode("UTF-8").strip()
        if not secret_token:
            raise RuntimeError(f"Secret '{name}' in Secret Manager is empty.")
        return secret_token
    except Exception as e:
        raise RuntimeError(
            f"Failed to retrieve FYERS access token from Secret Manager ({FYERS_ACCESS_TOKEN_SECRET_ID}): {e}"
        ) from e
