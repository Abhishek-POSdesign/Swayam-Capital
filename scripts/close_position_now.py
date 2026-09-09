"""Close an open paper position from this PC, at real prices.

WHY THIS EXISTS
---------------
On 2026-09-09 Abhishek opened his first ever paper position and found he could
not close it. Two reasons, both found that day:

  1. THERE IS NO CLOSE BUTTON ANYWHERE IN THE APP. `ActiveTradesComponent`
     carries the close UI and is imported by `web/src/main.js`, but it is never
     instantiated and no page has a mount point for it. The round-2 rebuild of
     Home and the desk dropped it, and nobody noticed because nobody had ever
     had a position.

  2. `/api/positions/live` and the close path both ask FYERS for the chain with
     `underlying="NIFTY"` and `timestamp=<a date string>`. FYERS answers
     "Please provide a valid symbol". It has never worked. That is why the live
     profit and loss reads unavailable, and why a close with no explicit prices
     fails.

This script goes round both. It reads the real chain the way the working market
route does, takes the traded price for each of his legs, and calls the SAME
close endpoint the app would call, so the real code path is exercised.

    .\\.venv\\Scripts\\python.exe scripts\\close_position_now.py            # show
    .\\.venv\\Scripts\\python.exe scripts\\close_position_now.py <id> go    # close
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from swayam.api.routes.market import resolve_expiry_epoch  # noqa: E402
from swayam.api.routes.positions import (  # noqa: E402
    ClosePositionRequest,
    close_position,
)
from swayam.db import db  # noqa: E402
from swayam.fyers_client import fyers_client  # noqa: E402


def _open_positions() -> list[dict]:
    return (
        db.client.table("swayam_positions")
        .select("*")
        .eq("provenance", "live")
        .eq("status", "open")
        .execute()
        .data
        or []
    )


def _live_prices(expiry_iso: str, wanted: set[tuple[float, str]]) -> dict[tuple[float, str], float]:
    """The traded price for each leg, from the real chain, read the working way."""
    base = fyers_client.get_option_chain(strike_count=2)
    epoch = resolve_expiry_epoch(base, expiry_iso)
    if not epoch:
        raise SystemExit(f"FYERS does not list an expiry on {expiry_iso}.")

    chain = fyers_client.get_option_chain(strike_count=40, timestamp=epoch)
    rows = chain.get("optionsChain") or []

    found: dict[tuple[float, str], float] = {}
    for row in rows:
        key = (float(row.get("strike_price") or 0.0), str(row.get("option_type") or ""))
        if key in wanted and row.get("ltp") is not None:
            found[key] = float(row["ltp"])
    return found


def main() -> int:
    positions = _open_positions()

    if len(sys.argv) < 3 or sys.argv[2] != "go":
        if not positions:
            print("Nothing open.")
            return 0
        print("open positions of yours:")
        for p in positions:
            print(f"\n  {p['id']}  {p.get('strategy_name')}  opened {str(p.get('opened_at'))[:16]}")
            for leg in p.get("legs") or []:
                print(
                    f"    {str(leg.get('direction')).upper():<5} {leg.get('strike'):.0f} "
                    f"{leg.get('option_type')}  entered at {leg.get('entry_premium')}"
                )
        print("\nTo close one, add its id and the word go:")
        print("  .\\.venv\\Scripts\\python.exe scripts\\close_position_now.py <id> go")
        return 0

    wanted_id = sys.argv[1]
    pos = next((p for p in positions if str(p["id"]) == wanted_id), None)
    if pos is None:
        print(f"No OPEN position of yours with id {wanted_id}.")
        return 1

    legs = pos.get("legs") or []
    expiry = pos.get("expiry_date") or (legs[0].get("expiry_date") if legs else None)
    if not expiry:
        print("This position has no expiry recorded, so it cannot be priced.")
        return 1

    wanted = {(float(l.get("strike") or 0.0), str(l.get("option_type") or "")) for l in legs}
    prices = _live_prices(str(expiry), wanted)

    missing = wanted - set(prices)
    if missing:
        print("FYERS has no traded price for these legs, so the close is refused:")
        for strike, opt in sorted(missing):
            print(f"  {strike:.0f} {opt}")
        print("Nothing was changed.")
        return 1

    exit_legs = []
    print("closing at these prices, read from FYERS just now:")
    for leg in legs:
        key = (float(leg.get("strike") or 0.0), str(leg.get("option_type") or ""))
        price = prices[key]
        print(
            f"  {str(leg.get('direction')).upper():<5} {key[0]:.0f} {key[1]}  "
            f"in at {leg.get('entry_premium')}  out at {price}"
        )
        exit_legs.append(
            {"strike": key[0], "option_type": key[1], "exit_premium": price}
        )

    request = ClosePositionRequest(
        close_reason="manual",
        notes="Closed from the PC because the app has no close button yet.",
        exit_legs=exit_legs,
    )

    print()
    result = close_position(wanted_id, request)

    print(f"status        : {result.status}")
    print(f"gross         : {result.gross_pnl_inr}")
    print(f"charges       : {result.total_charges_inr}")
    print(f"net realised  : {result.realized_pnl_inr}")
    print(f"note          : {result.journal_path or '(none recorded)'}")
    print()
    print("per leg:")
    for leg in result.exit_legs:
        print(
            f"  {str(leg.get('direction')).upper():<5} {leg.get('strike'):.0f} {leg.get('option_type')}"
            f"  gross {leg.get('gross_pnl_inr')}  charges {leg.get('charges_inr')}"
            f"  net {leg.get('net_pnl_inr')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
