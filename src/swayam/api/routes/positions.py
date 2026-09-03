"""
Portfolio and active positions endpoints for Swayam Capital.

Tracks open paper and live trades with dynamic mark-to-market P&L calculation.
"""

from typing import Any
from fastapi import APIRouter, HTTPException, Query
from swayam.api.models_api import PositionResponse
from swayam.db import db

router = APIRouter()

# In-memory store for paper positions in local mode
_local_paper_positions: list[dict[str, Any]] = []


def record_local_paper_position(pos: dict[str, Any]) -> None:
    """Stores a paper position locally when database is in offline or mock mode."""
    _local_paper_positions.append(pos)


@router.get("/api/positions", response_model=list[PositionResponse])
def get_positions(status: str = Query(default="open")) -> list[PositionResponse]:
    """Returns list of positions with current unrealized P&L."""
    positions_data: list[dict[str, Any]] = []

    # Attempt fetching from Supabase
    try:
        client = db.client
        res = client.table("positions").select("*").eq("status", status).execute()
        if res.data:
            positions_data.extend(res.data)
    except Exception:
        pass

    # Merge with local session paper trades if not already present
    existing_ids = {p.get("id") for p in positions_data}
    for local_pos in _local_paper_positions:
        if local_pos.get("id") not in existing_ids and local_pos.get("status") == status:
            positions_data.append(local_pos)

    results: list[PositionResponse] = []
    for p in positions_data:
        results.append(
            PositionResponse(
                id=str(p.get("id")),
                strategy_name=p.get("strategy_name", "Unknown Strategy"),
                underlying=p.get("underlying", "NIFTY"),
                legs=p.get("legs", []),
                net_debit_credit_inr=float(p.get("net_debit_credit_inr", 0.0)),
                max_loss_inr=float(p.get("max_loss_inr", 0.0)),
                max_profit_inr=float(p.get("max_profit_inr", 0.0)),
                breakeven_points=p.get("breakeven_points", []),
                status=p.get("status", "open"),
                mode=p.get("mode", "paper"),
                opened_at=str(p.get("opened_at")),
                unrealized_pnl_inr=float(p.get("unrealized_pnl_inr", 0.0)),
                journal_path=p.get("journal_path"),
            )
        )

    return results


@router.get("/api/positions/{position_id}/pnl-live")
def get_position_pnl_live(position_id: str) -> dict[str, Any]:
    """Returns live P&L snapshot for a specific position."""
    for pos in _local_paper_positions:
        if str(pos.get("id")) == position_id:
            return {
                "position_id": position_id,
                "unrealized_pnl_inr": float(pos.get("unrealized_pnl_inr", 0.0)),
                "status": pos.get("status", "open"),
            }

    try:
        client = db.client
        res = client.table("positions").select("*").eq("id", position_id).single().execute()
        if res.data:
            return {
                "position_id": position_id,
                "unrealized_pnl_inr": float(res.data.get("unrealized_pnl_inr", 0.0)),
                "status": res.data.get("status", "open"),
            }
    except Exception:
        pass

    raise HTTPException(status_code=404, detail=f"Position {position_id} not found.")
