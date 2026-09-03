"""
Central configuration module for Swayam Capital.

This module loads environment variables from `.env` using python-dotenv, validates
the presence of required configuration paths and keys, and exposes a typed singleton
`settings` object used throughout the application.
"""

from dataclasses import dataclass, field
from pathlib import Path
import os
from typing import Optional
from dotenv import load_dotenv

# Load .env file from project root if present
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    """Typed application settings loaded from environment variables."""

    # FYERS API
    fyers_client_id: str = field(default_factory=lambda: os.getenv("FYERS_CLIENT_ID", ""))
    fyers_app_id: str = field(default_factory=lambda: os.getenv("FYERS_APP_ID", ""))
    fyers_secret_key: str = field(default_factory=lambda: os.getenv("FYERS_SECRET_KEY", ""))
    fyers_redirect_uri: str = field(default_factory=lambda: os.getenv("FYERS_REDIRECT_URI", "http://localhost:8080/fyers-callback"))
    fyers_access_token: str = field(default_factory=lambda: os.getenv("FYERS_ACCESS_TOKEN", ""))

    # Supabase
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_anon_key: str = field(default_factory=lambda: os.getenv("SUPABASE_ANON_KEY", ""))
    supabase_service_role_key: str = field(default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))

    # Obsidian Vault Integration
    vault_path: Path = field(
        default_factory=lambda: Path(os.getenv("VAULT_PATH", r"G:\My Drive\Second Brain"))
    )
    trading_method_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("TRADING_METHOD_PATH", r"G:\My Drive\Second Brain\02 - Projects\Trading\01 - Method")
        )
    )
    trading_brief_path: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "TRADING_BRIEF_PATH",
                r"G:\My Drive\Second Brain\02 - Projects\Trading\00 - Reference\Personal Trading Brief.md",
            )
        )
    )
    daily_log_dir: Path = field(
        default_factory=lambda: Path(os.getenv("DAILY_LOG_DIR", r"G:\My Drive\Second Brain\01 - Daily Logs"))
    )

    # Local Data Cache Paths
    project_root: Path = field(default_factory=lambda: PROJECT_ROOT)
    local_data_dir: Path = field(
        default_factory=lambda: Path(os.getenv("LOCAL_DATA_DIR", str(PROJECT_ROOT / "data")))
    )
    bhavcopy_dir: Path = field(
        default_factory=lambda: Path(os.getenv("BHAVCOPY_DIR", str(PROJECT_ROOT / "data" / "bhavcopy")))
    )
    duckdb_path: Path = field(
        default_factory=lambda: Path(os.getenv("DUCKDB_PATH", str(PROJECT_ROOT / "data" / "options_cache.duckdb")))
    )

    # Trading Config
    risk_free_rate: float = field(
        default_factory=lambda: float(os.getenv("RISK_FREE_RATE", "0.068"))
    )
    default_tolerance_pct: float = field(
        default_factory=lambda: float(os.getenv("DEFAULT_TOLERANCE_PCT", "0.02"))
    )

    # AI Integration
    ai_provider: str = field(default_factory=lambda: os.getenv("AI_PROVIDER", "vertex"))
    ai_api_key: str = field(default_factory=lambda: os.getenv("AI_API_KEY", ""))
    ai_model: str = field(default_factory=lambda: os.getenv("AI_MODEL", "gemini-1.5-pro"))
    ai_fallback_provider: str = field(default_factory=lambda: os.getenv("AI_FALLBACK_PROVIDER", "direct"))
    ai_fallback_model: str = field(default_factory=lambda: os.getenv("AI_FALLBACK_MODEL", "claude-3-5-sonnet-20241022"))

    def validate_required_vars(self) -> list[str]:
        """Checks for missing required environment variables and returns a list of missing names."""
        missing: list[str] = []
        required = [
            ("FYERS_CLIENT_ID", self.fyers_client_id),
            ("FYERS_APP_ID", self.fyers_app_id),
            ("FYERS_SECRET_KEY", self.fyers_secret_key),
            ("SUPABASE_URL", self.supabase_url),
            ("SUPABASE_ANON_KEY", self.supabase_anon_key),
            ("VAULT_PATH", str(self.vault_path)),
            ("TRADING_METHOD_PATH", str(self.trading_method_path)),
        ]
        for name, val in required:
            if not val or val.strip() == "":
                missing.append(name)
        return missing


# Singleton settings instance
settings = Settings()
