"""
Supabase Operational Database Client for Swayam Capital.

Encapsulates cloud database connections for active positions, trade history,
daily operational readiness logs, and dynamic system configuration.
"""

from typing import Any, Optional
from supabase import Client, create_client
from swayam.config import settings


class DatabaseError(Exception):
    """Raised when an operation against the Supabase database fails."""
    pass


class SupabaseDB:
    """Wrapper managing connections and operations against Supabase."""

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None) -> None:
        self.url = url or settings.supabase_url
        self.key = key or settings.supabase_service_role_key or settings.supabase_anon_key
        self._client: Optional[Client] = None

    @property
    def client(self) -> Client:
        """Returns the initialized Supabase client, raising an error if credentials are missing."""
        if self._client is None:
            if not self.url or not self.key:
                raise DatabaseError(
                    "Supabase URL or Key not configured. Please set SUPABASE_URL and SUPABASE_ANON_KEY in .env."
                )
            try:
                self._client = create_client(self.url, self.key)
            except Exception as e:
                raise DatabaseError(f"Failed to connect to Supabase at {self.url}: {e}") from e
        return self._client

    def get_config(self, key: str, default: Any = None) -> Any:
        """Retrieves a configuration value from the `config` table.

        Args:
            key: Config key name (e.g. 'margin_base_inr').
            default: Fallback value if key is not found.

        Returns:
            Any: The stored config value.
        """
        try:
            res = self.client.table("config").select("value").eq("key", key).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]["value"]
            return default
        except Exception as e:
            # Fall back to default if table isn't migrated yet
            return default

    def set_config(self, key: str, value: Any, updated_by: str = "swayam") -> None:
        """Inserts or updates a configuration key in the `config` table.

        Args:
            key: Config key name.
            value: JSON-serializable value.
            updated_by: Identifier of the component or user making the change.
        """
        payload = {"key": key, "value": value, "updated_by": updated_by}
        self.client.table("config").upsert(payload).execute()

    def get_margin_base_inr(self, fallback: float = 850000.0) -> float:
        """Convenience method to retrieve current margin base in INR."""
        val = self.get_config("margin_base_inr", fallback)
        try:
            return float(val)
        except (ValueError, TypeError):
            return fallback


# Global database instance
db = SupabaseDB()
