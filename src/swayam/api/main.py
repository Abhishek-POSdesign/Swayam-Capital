"""
FastAPI application entry point for Swayam Capital.

Initializes REST API routes, CORS middleware, and WebSocket broadcasting services.
"""

import asyncio
import contextlib
import os
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from swayam.api.routes import ai, execution, health, home, journal, lessons, macro, market, notebook, notifications, orders, pinned, positions, readiness, session, strategy, tts, validation
from swayam.api.chain_feed import chain_feed
from swayam.api.spot_feed import SpotFeed
from swayam.api.ws_manager import ws_manager
from swayam.fyers_client import fyers_client
from swayam.services import order_watcher


async def _broadcast_tick(frame: dict[str, Any]) -> None:
    """Pushes a tick to the browsers, and hands the REST endpoint the same price.

    The REST spot endpoint keeps a 3-second cache. Filling it from the feed
    means a page that polls REST while the market is open costs no extra
    FYERS call in the process that holds the feed.
    """
    market._spot_cache["data"] = {"spot": frame["spot"], "as_of": frame["as_of"]}
    market._spot_cache["timestamp"] = time.time()
    await ws_manager.broadcast_spot(frame)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """Starts the two background feeds that keep real prices flowing.

    The spot feed pushes NIFTY ticks to the browsers. The chain feed keeps the
    option chains the desk is watching fresh, at one FYERS call per expiry
    however many legs or browsers are looking, so a browser poll never becomes
    a broker call.

    SWAYAM_DISABLE_SPOT_FEED=1 keeps both off, which the test suite sets so no
    test ever polls the live broker in the background.
    """
    tasks: list[Any] = []
    if os.getenv("SWAYAM_DISABLE_SPOT_FEED") != "1":
        feed = SpotFeed(fyers_client.get_nifty_spot, _broadcast_tick)
        app.state.spot_feed = feed
        tasks.append(asyncio.create_task(feed.run(), name="swayam-spot-feed"))
        app.state.chain_feed = chain_feed
        tasks.append(asyncio.create_task(chain_feed.run(), name="swayam-chain-feed"))
        # Build B. The resting-order watcher rides on the chain feed's
        # refreshes and never makes a FYERS request of its own, so his waiting
        # limits are checked against the same book the desk is quoting from.
        # It only fills while this process is awake and the feed is reading.
        order_watcher.register(chain_feed)
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title="Swayam Capital API",
    description="Rule-enforced algorithmic and paper options trading platform",
    version="0.5.0",
    lifespan=lifespan,
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
app.include_router(home.router)
app.include_router(macro.router)
app.include_router(market.router)
app.include_router(strategy.router)
app.include_router(validation.router)
app.include_router(execution.router)
app.include_router(positions.router)
app.include_router(orders.router)
app.include_router(readiness.router)
app.include_router(ai.router)
app.include_router(tts.router)
app.include_router(notebook.router)
app.include_router(pinned.router)
app.include_router(session.router)
app.include_router(journal.router)
app.include_router(lessons.router)
app.include_router(notifications.router)

@app.get("/api/market/spot-feed/status", include_in_schema=False)
async def spot_feed_status() -> dict[str, Any]:
    """What the tick feed in THIS worker is doing. For checking, not for display.

    Registered before the SPA catch-all below, which answers 404 for any
    unknown /api path.
    """
    feed = getattr(app.state, "spot_feed", None)
    if feed is None:
        return {"running": False, "reason": "the feed is disabled in this process"}
    return {"running": True, "pid": os.getpid(), "checked_at": datetime.now(timezone.utc).isoformat(), **feed.status()}


# Serve frontend static files from built dist if present (Cloud Run & production)
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_web_dist = Path(__file__).resolve().parents[3] / "web" / "dist"
if _web_dist.exists():
    _assets_dir = _web_dist / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="API endpoint not found")

        candidate = _web_dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)

        index_html = _web_dist / "index.html"
        if not index_html.exists():
            raise HTTPException(status_code=404, detail="Frontend not built")
        return FileResponse(index_html)



@app.websocket("/ws/spot")
async def websocket_spot_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint broadcasting real-time NIFTY 50 spot ticks."""
    await ws_manager.connect_spot(websocket)
    # The browser gets the latest tick the moment it connects, so a page that
    # opens mid-session is not blank until the next poll.
    feed = getattr(app.state, "spot_feed", None)
    if feed is not None and feed.last_tick:
        with contextlib.suppress(Exception):
            await websocket.send_json(feed.last_tick)
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
