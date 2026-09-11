r"""Open ONE sold leg, read the row back, close it, and print the note.

WHY THIS SCRIPT EXISTS
----------------------
Round 1b made `max_loss_inr` nullable, because `math.inf` in a numeric column
is what stopped him recording a naked single leg on 11 September 2026. The
review of that branch found two more places downstream that assumed the figure
was a number, and a sweep found a third. All four are covered by
`tests/api/test_naked_trade_lifecycle.py`.

What no test can do is run the whole thing against the real broker, because a
leg only fills while the market is open. HE asked for that proof, and it can
only happen in his window. This is that run, in one command.

WHAT IT CREATES, said plainly before you run it
-----------------------------------------------
One real position, one lot, sold, at the market. It fills at the broker's bid
and it books real charges. While paper trading has not started it is written
`provenance = 'terminal_test'` and its note goes to `04 - Journal/Terminal
tests/`, so it stays out of the record his paper results are judged against.
It is closed again seconds later, in the same run.

It is a REAL trade with a REAL cost: one round trip of charges, roughly sixty
rupees on a cheap option, plus whatever the spread takes. Nothing about it is
simulated.

USAGE
-----
    .\.venv\Scripts\python.exe scripts\prove_naked_trade.py            # dry
    .\.venv\Scripts\python.exe scripts\prove_naked_trade.py --apply    # real

Dry by default, like `scripts/mark_terminal_tests.py`. It refuses outside
market hours rather than half-running.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://localhost:8000"


def get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.load(r)


def post(path: str, body: dict):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually send it")
    args = ap.parse_args()

    health = get("/api/market/data-health")
    print(f"market    : {health['headline']}  ({health['ist_time']} IST)")
    if not health.get("market_open"):
        print()
        print("REFUSED. Nothing fills while the market is shut, so this would")
        print("prove nothing. Run it between 09:15 and 15:30 IST -- in his")
        print("window, 13:00 to 14:30, is fine.")
        return 2

    phase = get("/api/phase")
    testing = not phase.get("paper_trading_started")
    print(f"phase     : {'terminal testing' if testing else 'PAPER TRADING HAS STARTED'}")

    exp = get("/api/market/expiries")
    weekly = exp["weekly_expiry"]
    spot = get("/api/nifty/spot").get("spot")
    chain = get(f"/api/option-chain?expiry={weekly}&strike_count=30")
    target = spot + 300
    row = min(chain["strikes"], key=lambda r: abs(r["strike"] - target))
    strike, ce = row["strike"], row["ce"]
    print(f"NIFTY     : {spot}")
    print(f"the leg   : SELL 1 lot  {strike:,.0f} CE  {weekly}   bid {ce.get('bid')} / ask {ce.get('ask')}")
    print()

    if not args.apply:
        print("DRY RUN. Nothing was sent. Add --apply to send it for real.")
        print("It will open one sold call, read the row back, close it, and")
        print("print the note. Expect one round trip of charges.")
        return 0

    status, opened = post("/api/execute/multi-leg", {
        "strategy_name": "Naked short call, round 1b proof",
        "underlying": "NIFTY", "current_spot": spot,
        "execution_mode": "all_at_once",
        "legs": [{"strike": strike, "option_type": "CE", "direction": "sell",
                  "quantity_lots": 1, "order_type": "MARKET",
                  "expiry_date": weekly}],
    })
    if status != 200:
        print(f"OPEN REFUSED, HTTP {status}")
        print(json.dumps(opened, indent=2)[:1200])
        return 1

    pid = opened["position_id"]
    print(f"OPENED    : {pid}")
    print(f"  max_loss_inr on the reply : {opened.get('max_loss_inr')!r}   <- None means no ceiling")
    print(f"  journal                   : {opened.get('journal_status')}  {opened.get('journal_path')}")

    live = [p for p in get("/api/positions/live") if p["position_id"] == pid]
    if live:
        p = live[0]
        print("  READ BACK FROM THE DATABASE:")
        print(f"    max_loss_inr              : {p.get('max_loss_inr')!r}")
        print(f"    max_loss_unbounded_reason : {p.get('max_loss_unbounded_reason')}")
    else:
        print("  the row could not be read back from /api/positions/live")

    time.sleep(2)
    status, closed = post(f"/api/positions/{pid}/close", {"close_reason": "manual",
                                                          "notes": "round 1b proof"})
    if status != 200:
        print(f"\nCLOSE REFUSED, HTTP {status}   <- THIS is the fault this build fixed")
        print(json.dumps(closed, indent=2)[:1200])
        return 1

    print(f"\nCLOSED    : net {closed.get('realized_pnl_inr')}  charges {closed.get('total_charges_inr')}")

    rel = closed.get("journal_path") or opened.get("journal_path")
    if rel:
        from swayam.config import settings
        note = Path(settings.vault_path) / rel
        print(f"\nTHE NOTE  : {note}")
        if note.exists():
            text = note.read_text(encoding="utf-8")
            for line in text.splitlines():
                if any(k in line for k in ("Max loss", "R:R implied", "% of max risk")):
                    print(f"    {line.strip()}")
        else:
            print("    not written yet; run scripts/drain_journal_outbox.py")

    print(f"\nThis was a REAL trade, marked {'terminal_test' if testing else 'live'}.")
    print(f"Its id is {pid}. Nothing else was touched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
