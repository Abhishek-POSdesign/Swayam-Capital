"""
FYERS API v3 Broker Client Wrapper for Swayam Capital.

Encapsulates authentication, account profile inspection, live spot quotes,
option chain snapshots, and WebSocket streaming feeds from FYERS.
Execution methods (order placement/modification) are deferred to Phase 2.
"""

from typing import Any, Callable, Optional
from fyers_apiv3 import fyersModel
from swayam.config import settings


class FyersClientError(Exception):
    """Raised when FYERS API requests fail or credentials are unauthorized."""
    pass


class FyersClient:
    """Wrapper managing REST and WebSocket communication with FYERS API v3."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        app_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> None:
        self.client_id = client_id or settings.fyers_client_id
        self.app_id = app_id or settings.fyers_app_id
        self.secret_key = secret_key or settings.fyers_secret_key
        self.access_token = access_token or settings.fyers_access_token
        self._model: Optional[fyersModel.FyersModel] = None

    @property
    def model(self) -> fyersModel.FyersModel:
        """Returns the initialized FyersModel REST client instance."""
        if self._model is None:
            if not self.access_token or not self.app_id:
                raise FyersClientError(
                    "FYERS access token or App ID not configured. Please run `python scripts/generate_fyers_token.py`."
                )
            self._model = fyersModel.FyersModel(
                client_id=self.app_id,
                token=self.access_token,
                is_async=False,
                log_path="",
            )
        return self._model

    def get_profile(self) -> dict[str, Any]:
        """Fetches account profile details to verify active API authentication."""
        try:
            response = self.model.get_profile()
            if response.get("s") == "ok":
                return response.get("data", {})
            raise FyersClientError(f"FYERS profile check failed: {response.get('message', response)}")
        except Exception as e:
            raise FyersClientError(f"FYERS connection error: {e}") from e

    def get_nifty_spot(self) -> float:
        """Fetches the current real-time NIFTY 50 spot index price."""
        symbol = "NSE:NIFTY50-INDEX"
        data = {"symbols": symbol}
        try:
            response = self.model.quotes(data=data)
            if response.get("s") == "ok" and "d" in response:
                quotes = response["d"]
                if len(quotes) > 0 and "v" in quotes[0]:
                    return float(quotes[0]["v"]["lp"])
            raise FyersClientError(f"Failed to fetch NIFTY spot quote: {response}")
        except Exception as e:
            raise FyersClientError(f"NIFTY spot price fetch failed: {e}") from e

    def get_option_chain(
        self,
        underlying: str = "NSE:NIFTY50-INDEX",
        strike_count: int = 20,
        timestamp: Optional[str] = None,
    ) -> dict[str, Any]:
        """Fetches the live options chain snapshot for an underlying instrument.

        Args:
            underlying: Underlying symbol (default: 'NSE:NIFTY50-INDEX').
            strike_count: Number of strikes around ATM to return (max 50).
            timestamp: Specific expiry timestamp if filtering by expiry.

        Returns:
            dict[str, Any]: Chain data with strikes, LTP, bid/ask, and OI.
        """
        data: dict[str, Any] = {
            "symbol": underlying,
            "strikecount": min(strike_count, 50),
        }
        if timestamp:
            data["timestamp"] = timestamp

        try:
            response = self.model.optionchain(data=data)
            if response.get("s") == "ok":
                return response.get("data", {})
            raise FyersClientError(f"Option chain query failed: {response.get('message', response)}")
        except Exception as e:
            raise FyersClientError(f"Option chain request error: {e}") from e

    def get_historical_candles(
        self,
        symbol: str,
        resolution: str,
        date_format: str = "1",
        range_from: str = "",
        range_to: str = "",
        cont_flag: str = "1",
    ) -> dict[str, Any]:
        """Fetches historical OHLCV candlestick data from FYERS.

        Args:
            symbol: Trading symbol, e.g. "NSE:NIFTY50-INDEX".
            resolution: Candle resolution — "15" (15m), "60" (1h), "D" (daily).
            date_format: "1" for date string (YYYY-MM-DD), "0" for epoch.
            range_from: Start date/epoch.
            range_to: End date/epoch.
            cont_flag: "1" to include continuous data.

        Returns:
            dict with key "candles": list of [timestamp, open, high, low, close, volume].

        Raises:
            FyersClientError: On API error or unauthenticated request.
        """
        data: dict[str, Any] = {
            "symbol": symbol,
            "resolution": resolution,
            "date_format": date_format,
            "range_from": range_from,
            "range_to": range_to,
            "cont_flag": cont_flag,
        }
        try:
            response = self.model.history(data=data)
            if response.get("s") == "ok":
                return response  # contains "candles" key
            raise FyersClientError(
                f"FYERS historical data fetch failed: {response.get('message', response)}"
            )
        except Exception as e:
            raise FyersClientError(f"FYERS historical candles request error: {e}") from e

    def stream_ticks(
        self,
        symbols: list[str],
        on_tick: Callable[[dict[str, Any]], None],
    ) -> Any:
        """Initializes a WebSocket connection streaming live tick updates.

        Args:
            symbols: List of trading symbols (max 200).
            on_tick: Callback function invoked with each incoming tick payload.

        Returns:
            FyersDataSocket: Active socket instance.
        """
        from fyers_apiv3.FyersWebsocket import data_ws

        def on_message(message: dict[str, Any]) -> None:
            on_tick(message)

        def on_error(message: str) -> None:
            pass

        def on_close(message: str) -> None:
            pass

        def on_open() -> None:
            fyers_socket.subscribe(symbols=symbols, data_type="symbolUpdate")
            fyers_socket.keep_running()

        fyers_socket = data_ws.FyersDataSocket(
            access_token=f"{self.app_id}:{self.access_token}",
            log_path="",
            litemode=False,
            write_to_file=False,
            reconnect=True,
            on_connect=on_open,
            on_close=on_close,
            on_error=on_error,
            on_message=on_message,
        )
        return fyers_socket


# Global FYERS client instance
fyers_client = FyersClient()
