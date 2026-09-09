"""
Marks his trades that were filled at the traded price, so the record says so.

WHY THIS IS A SCRIPT AND NOT A MIGRATION
-----------------------------------------
A schema change is a migration. A one-off change to his real rows is not: it
is written as a script, it says what it will do, and he runs it. Global rule.

WHAT IT DOES
------------
From docs/PLAN.md 2.12.2 PR 2, realistic fills: from PR 2 on, a buy fills at
the ask and a sell at the bid. Everything before was filled at the last traded
price, and the two are NOT comparable. His three paper trades of 2026-09-09
(and anything else he took before PR 2 merged) carry `fill_basis` NULL or
'traded_price'. This sets NULL to 'traded_price' on rows that are his, so the
journal can show it and nothing after PR 2 is ever summed with them as if
alike.

It touches ONLY rows with provenance = 'live' and fill_basis IS NULL. The 81
quarantined build-test rows are left alone. It never touches a row that
already says what it was filled at.

    python scripts/mark_traded_price_fills.py            # shows what it would change
    python scripts/mark_traded_price_fills.py --apply    # changes it
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from swayam.db import db  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="write the change; without it, only show it")
    args = parser.parse_args()

    rows = (
        db.client.table("swayam_positions")
        .select("id,strategy_name,opened_at,status,fill_basis,provenance")
        .eq("provenance", "live")
        .execute()
        .data
        or []
    )
    todo = [r for r in rows if r.get("fill_basis") is None]
    already = [r for r in rows if r.get("fill_basis") is not None]

    print(f"rows that are his: {len(rows)}")
    print(f"already marked   : {len(already)}")
    print(f"to mark          : {len(todo)}")
    for r in todo:
        print(f"  {str(r['id'])[:8]}  {r.get('opened_at', '')[:16]}  {r.get('status'):<7} {r.get('strategy_name')}")

    if not todo:
        print("Nothing to do.")
        return 0
    if not args.apply:
        print("\nDry run. Nothing was written. Run again with --apply to mark these as filled at the traded price.")
        return 0

    ids = [r["id"] for r in todo]
    res = (
        db.client.table("swayam_positions")
        .update({"fill_basis": "traded_price"})
        .in_("id", ids)
        .execute()
    )
    changed = len(res.data or [])
    print(f"\nMarked {changed} row(s) as filled at the traded price, not comparable with fills at the bid and ask.")
    check = (
        db.client.table("swayam_positions").select("id").eq("provenance", "live").is_("fill_basis", "null").execute().data
        or []
    )
    print(f"Rows of his still unmarked: {len(check)}")
    return 0 if changed == len(ids) else 1


if __name__ == "__main__":
    raise SystemExit(main())
