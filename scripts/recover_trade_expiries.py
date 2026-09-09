"""Works out which expiry each of his historical legs was, from the prices.

None of his 21 trade notes records an expiry. For a calendar that is fatal:
Trade-07 sells the 18700 call and buys the 18700 call, and the only thing
separating them is an expiry nobody wrote down.

But the premium he paid IS the evidence. On the day he opened the trade, every
listed expiry at that strike traded in its own price range, and those ranges are
far apart. Ask which expiry's range on that day contains the premium he recorded,
and usually exactly one does.

    .\\.venv\\Scripts\\python.exe scripts\\recover_trade_expiries.py
    .\\.venv\\Scripts\\python.exe scripts\\recover_trade_expiries.py --csv out.csv

This does two jobs at once, and the second matters more than the first.
Recovering the expiry makes his trades replayable. But a leg whose premium
matches NO expiry's range is telling us either that his note is wrong or that
our data is wrong, and either way it must be found before a backtester is built
on top of it.

READ ONLY. It writes no vault note, no database row, and nothing over his
records. Its output is a report and an optional CSV.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from swayam.config import settings  # noqa: E402
from swayam.research.historical_trades import Leg, load_all  # noqa: E402
from swayam.research.store import HistoryStore  # noqa: E402

TRADES_SUBPATH = Path("02 - Projects") / "Trading" / "00 - Reference" / "Historical Swing Trades"
# A premium is quoted to five paise. Allow a little more than that before
# calling a match, because his sheet rounds and the day's range is a range.
TOLERANCE = 0.5


def load_eod(store: HistoryStore) -> pd.DataFrame:
    files = sorted((store.root / "options_eod").glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    frame = pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.date
    frame["expiry_date"] = pd.to_datetime(frame["expiry_date"]).dt.date
    return frame


def candidates_for(
    eod: pd.DataFrame, when: date, strike: float, option_type: str
) -> pd.DataFrame:
    return eod[
        (eod["trade_date"] == when)
        & (eod["strike"] == strike)
        & (eod["option_type"] == option_type)
        & (eod["expiry_date"] >= when)
    ].sort_values("expiry_date")


def match_leg(eod: pd.DataFrame, when: date, leg: Leg) -> dict[str, object]:
    """Which expiries could have produced the premium he recorded."""
    premium = abs(leg.premium)
    rows = candidates_for(eod, when, leg.strike, leg.option_type)
    if rows.empty:
        return {"expiries_listed": 0, "matches": [], "verdict": "no contract in the data"}

    inside = rows[
        (rows["low"] - TOLERANCE <= premium) & (premium <= rows["high"] + TOLERANCE)
    ]
    # A day with no trade has an open, high and low of zero but still carries a
    # close, so fall back to the closest close rather than call it a miss.
    traded = rows[(rows["high"] > 0)]
    matches = list(inside["expiry_date"])

    nearest_expiry = None
    nearest_gap = None
    if not rows.empty:
        gaps = (rows["close"] - premium).abs()
        nearest_expiry = rows.loc[gaps.idxmin(), "expiry_date"]
        nearest_gap = float(gaps.min())

    if len(matches) == 1:
        verdict = "one expiry"
    elif len(matches) > 1:
        verdict = f"{len(matches)} expiries"
    elif nearest_gap is not None and nearest_gap <= TOLERANCE:
        matches, verdict = [nearest_expiry], "one expiry, on the close"
    else:
        verdict = "no expiry matches his premium"

    return {
        "expiries_listed": len(rows),
        "expiries_traded": len(traded),
        "matches": matches,
        "verdict": verdict,
        "nearest_expiry": nearest_expiry,
        "nearest_gap": nearest_gap,
    }


def resolve_by_structure(
    trade, per_leg: list[dict[str, object]]
) -> tuple[list[dict[str, object]], str]:
    """Narrows the remaining ambiguity using what the structure itself demands.

    Prices alone leave some legs matching two or three expiries, because two
    adjacent weeklies can trade through the same premium on the same day. The
    shape of the trade settles most of them:

    - A CONDOR or a VERTICAL has every leg in ONE expiry. So the answer is the
      expiry that appears in every leg's candidate set.
    - A CALENDAR sells the near expiry and buys a later one at the same strike.
      That is his own rule, written in Trade-01: "Sell CE/PE for the next week
      expiry, Buy CE/PE for further week expiry". So the sold legs share the
      earliest expiry they all allow, and the bought legs share the earliest
      one they allow that is strictly later.

    Nothing here overrides a leg that the prices already pinned to exactly one
    expiry. This only chooses among candidates the prices already permitted.
    """
    def candidates(entry: dict[str, object]) -> set:
        return set(entry["all_matches"].split("|")) - {""}

    if not trade.is_calendar:
        shared = None
        for entry in per_leg:
            options = candidates(entry)
            shared = options if shared is None else (shared & options)
        if shared and len(shared) == 1:
            only = next(iter(shared))
            for entry in per_leg:
                if entry["recovered_expiry"] is None and only in candidates(entry):
                    entry["recovered_expiry"] = only
                    entry["verdict"] = "one expiry, settled by the structure"
            return per_leg, "every leg shares one expiry"
        return per_leg, "the legs share no single expiry"

    sold = [e for e in per_leg if e["action"] == "SELL"]
    bought = [e for e in per_leg if e["action"] == "BUY"]

    def earliest_shared(entries: list[dict[str, object]], after: str | None = None):
        shared = None
        for entry in entries:
            options = candidates(entry)
            shared = options if shared is None else (shared & options)
        if not shared:
            return None
        allowed = sorted(o for o in shared if after is None or o > after)
        return allowed[0] if allowed else None

    near = earliest_shared(sold)
    far = earliest_shared(bought, after=near)
    for entry in sold:
        if entry["recovered_expiry"] is None and near and near in candidates(entry):
            entry["recovered_expiry"] = near
            entry["verdict"] = "near leg, settled by the structure"
    for entry in bought:
        if entry["recovered_expiry"] is None and far and far in candidates(entry):
            entry["recovered_expiry"] = far
            entry["verdict"] = "far leg, settled by the structure"

    if near and far:
        return per_leg, f"calendar: sells {near}, buys {far}"
    return per_leg, "calendar: the two expiries could not be separated"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv")
    parser.add_argument("--root")
    args = parser.parse_args()

    folder = Path(settings.vault_path) / TRADES_SUBPATH
    trades = load_all(folder)
    store = HistoryStore(Path(args.root) if args.root else None)
    eod = load_eod(store)
    if eod.empty:
        raise SystemExit("No end-of-day option data on disk. Run load_nse_options_eod.py first.")

    print("\nRecovering the expiries his notes never recorded")
    print("=" * 78)
    print(f"  matching each opening leg's premium against every expiry listed at that")
    print(f"  strike on the day he opened, within ₹{TOLERANCE:.2f}")
    print("=" * 78)

    rows: list[dict[str, object]] = []
    solved = ambiguous = unmatched = skipped = 0

    for trade in trades:
        if trade.entry_date is None or not trade.legs:
            skipped += 1
            continue
        per_leg: list[dict[str, object]] = []
        for leg in trade.legs:
            result = match_leg(eod, trade.entry_date, leg)
            matches = result["matches"]
            per_leg.append({
                "trade_id": trade.trade_id, "entry_date": trade.entry_date,
                "strategy": trade.strategy, "is_calendar": trade.is_calendar,
                "action": leg.action, "option_type": leg.option_type,
                "strike": leg.strike, "premium": abs(leg.premium),
                "quantity": leg.quantity, "is_hedge": leg.is_hedge,
                "expiries_listed": result["expiries_listed"],
                "recovered_expiry": str(matches[0]) if len(matches) == 1 else None,
                "all_matches": "|".join(str(m) for m in matches),
                "verdict": result["verdict"],
                "nearest_expiry": result["nearest_expiry"],
                "nearest_gap": result["nearest_gap"],
            })

        per_leg, structure_note = resolve_by_structure(trade, per_leg)
        print(f"\n  Trade-{trade.trade_id:02d}  {trade.entry_date}  {trade.strategy}"
              f"{'   [CALENDAR]' if trade.is_calendar else ''}   {structure_note}")
        for entry in per_leg:
            if entry["recovered_expiry"]:
                solved += 1
                shown = str(entry["recovered_expiry"])
            elif entry["all_matches"]:
                ambiguous += 1
                shown = " or ".join(entry["all_matches"].split("|")[:3])
            else:
                unmatched += 1
                shown = "-"
            print(f"    {entry['action']:<4} {entry['option_type']} {entry['strike']:>8,.0f} "
                  f"@ ₹{entry['premium']:>8.2f}  ->  {shown:<34} {entry['verdict']}")
        rows.extend(per_leg)

    total = solved + ambiguous + unmatched
    print("\n" + "=" * 78)
    print(f"  legs examined            {total}")
    print(f"  expiry recovered exactly {solved:>4}   {100 * solved / total if total else 0:.0f}%")
    print(f"  more than one expiry fit {ambiguous:>4}")
    print(f"  no expiry fits           {unmatched:>4}")
    print(f"  trades skipped           {skipped:>4}   (no entry date or no legs in the note)")

    if unmatched:
        print("\n  A LEG THAT MATCHES NO EXPIRY IS A WARNING, NOT A CURIOSITY.")
        print("    Either his note has the premium wrong, or our data is wrong for that")
        print("    contract. Both have to be settled before a backtester is trusted on")
        print("    these trades, because they are the acceptance test.")

    calendars = [t for t in trades if t.is_calendar]
    print(f"\n  {len(calendars)} of {len(trades)} trades are calendars, and they are the ones")
    print("    that could not be replayed at all without this.")
    print("=" * 78)

    if args.csv:
        pd.DataFrame(rows).to_csv(args.csv, index=False)
        print(f"\n  Written to {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
