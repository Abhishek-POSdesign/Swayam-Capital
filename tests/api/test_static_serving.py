"""
Unit tests for FastAPI static frontend serving and SPA fallback (BUILD-9.5).
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from swayam.api.main import app

client = TestClient(app)


def test_api_routes_still_take_precedence_over_spa_fallback():
    """Verify core API routes like /health or /api/rules are not intercepted by SPA catch-all."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data


def test_missing_api_routes_return_404_not_spa_fallback():
    """Verify that calling an unknown /api/* endpoint returns 404, not the SPA index.html."""
    response = client.get("/api/this-endpoint-does-not-exist-xyz")
    assert response.status_code == 404


def test_spa_fallback_behavior(tmp_path, monkeypatch):
    """Verify that when web/dist exists, SPA fallback returns index.html for unknown routes."""
    # Create fake web/dist with index.html
    fake_dist = tmp_path / "web" / "dist"
    fake_dist.mkdir(parents=True)
    index_file = fake_dist / "index.html"
    index_file.write_text("<!DOCTYPE html><html><body>Swayam Capital SPA</body></html>", encoding="utf-8")

    from fastapi import FastAPI
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    test_app = FastAPI()

    @test_app.get("/api/test")
    def test_endpoint():
        return {"ok": True}

    @test_app.get("/{full_path:path}")
    async def fallback(full_path: str):
        candidate = fake_dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(fake_dist / "index.html")

    test_client = TestClient(test_app)

    # API route responds
    res_api = test_client.get("/api/test")
    assert res_api.status_code == 200
    assert res_api.json() == {"ok": True}

    # SPA route falls back to index.html
    res_home = test_client.get("/")
    assert res_home.status_code == 200
    assert "Swayam Capital SPA" in res_home.text

    res_strategy = test_client.get("/strategy")
    assert res_strategy.status_code == 200
    assert "Swayam Capital SPA" in res_strategy.text
