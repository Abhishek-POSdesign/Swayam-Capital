"""
WebSocket connection manager for Swayam Capital live data broadcasting.

Maintains active browser client connections and broadcasts live market ticks and
portfolio P&L updates asynchronously.
"""

from typing import Any
from fastapi import WebSocket


class WebSocketManager:
    """Manages active WebSocket client connections."""

    def __init__(self) -> None:
        self.active_spot_connections: list[WebSocket] = []
        self.active_position_connections: dict[str, list[WebSocket]] = {}

    async def connect_spot(self, websocket: WebSocket) -> None:
        """Accepts and registers a new WebSocket client for live spot ticks."""
        await websocket.accept()
        self.active_spot_connections.append(websocket)

    def disconnect_spot(self, websocket: WebSocket) -> None:
        """Removes a disconnected spot tick client."""
        if websocket in self.active_spot_connections:
            self.active_spot_connections.remove(websocket)

    async def broadcast_spot(self, message: dict[str, Any]) -> None:
        """Broadcasts spot updates to all connected browser clients."""
        disconnected = []
        for connection in self.active_spot_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect_spot(connection)

    async def connect_position(self, position_id: str, websocket: WebSocket) -> None:
        """Accepts and registers a new WebSocket client for a specific position P&L stream."""
        await websocket.accept()
        if position_id not in self.active_position_connections:
            self.active_position_connections[position_id] = []
        self.active_position_connections[position_id].append(websocket)

    def disconnect_position(self, position_id: str, websocket: WebSocket) -> None:
        """Removes a disconnected position client."""
        if position_id in self.active_position_connections:
            if websocket in self.active_position_connections[position_id]:
                self.active_position_connections[position_id].remove(websocket)

    async def broadcast_position(self, position_id: str, message: dict[str, Any]) -> None:
        """Broadcasts P&L updates to clients watching a position."""
        if position_id not in self.active_position_connections:
            return

        disconnected = []
        for connection in self.active_position_connections[position_id]:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for connection in disconnected:
            self.disconnect_position(position_id, connection)


ws_manager = WebSocketManager()
