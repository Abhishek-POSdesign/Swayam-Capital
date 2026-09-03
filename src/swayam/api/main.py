"""
FastAPI application entry point for Swayam Capital.

Initializes REST API routes, CORS middleware, and WebSocket broadcasting services.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from swayam.api.routes import execution, health, market, positions, readiness, strategy, validation
from swayam.api.ws_manager import ws_manager

app = FastAPI(
    title="Swayam Capital API",
    description="Rule-enforced algorithmic and paper options trading platform",
    version="0.4.0",
)

# Enable CORS for local Vite dev server and browser clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register REST route blueprints
app.include_router(health.router)
app.include_router(market.router)
app.include_router(strategy.router)
app.include_router(validation.router)
app.include_router(execution.router)
app.include_router(positions.router)
app.include_router(readiness.router)


@app.websocket("/ws/spot")
async def websocket_spot_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint broadcasting real-time NIFTY 50 spot ticks."""
    await ws_manager.connect_spot(websocket)
    try:
        while True:
            # Keep-alive loop
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect_spot(websocket)
    except Exception:
        ws_manager.disconnect_spot(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("swayam.api.main:app", host="0.0.0.0", port=8000, reload=True)
