"""
FastAPI application entry point for Swayam Capital.

Initializes REST API routes, CORS middleware, and WebSocket broadcasting services.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from swayam.api.routes import ai, execution, health, journal, lessons, market, notebook, pinned, positions, readiness, session, strategy, tts, validation
from swayam.api.ws_manager import ws_manager

app = FastAPI(
    title="Swayam Capital API",
    description="Rule-enforced algorithmic and paper options trading platform",
    version="0.5.0",
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
app.include_router(ai.router)
app.include_router(tts.router)
app.include_router(notebook.router)
app.include_router(pinned.router)
app.include_router(session.router)
app.include_router(journal.router)
app.include_router(lessons.router)

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
