"""Labels NIFTY's daily chart with HIS market cycles, and measures what it found.

This is a MEASUREMENT script, not the backtester. Its whole purpose is to answer
one question before anything is built on top of a definition: does the definition
catch anything real? A cycle name that matches nothing, or matches four days in
five, is words rather than a rule, and he asked to be told that before any work
rests on it.

HIS DEFINITIONS, given 2026-09-12. Quoted lines are his.

  SQUEEZE   "the daily range shrinking, so the last five to ten days' high-to-low
            is smaller than the 20-day average; price making no new 10-day high
            or low, staying inside a band; and India VIX low or falling."
            "the first two define a squeeze, the VIX confirms it."
  EXPANDING sideways, but "expanding both ways" rather than contracting.
  TRENDING  bullish or bearish, and within that "aggressive" or "basic".
  LENGTH    "A cycle needs at least five trading days, one week, to count."

WHAT HE HAS NOT YET PINNED DOWN, and the script measures rather than guesses:

  1. "Last five to ten days' high-to-low smaller than the 20-day average" has two
     honest readings, and they are different measurements. Both are computed and
     reported side by side as CONTRACTION_A and CONTRACTION_B so he can say which
     one his eye is doing.
       A  the average of each day's own high-minus-low over 5 days, against the
          same average over 20 days. A candle-size measure.
       B  the band traced by the last 10 days, highest high minus lowest low,
          against the average of that same band over the past 20 days. A
          territory measure.
  2. Aggressive against basic trending has no threshold from him. The script
     reports the distribution of trend strength across trending days and splits
     at its median, clearly marked as a PLACEHOLDER split awaiting his number.

Usage:
    .\\.venv\\Scripts\\python.exe scripts\\label_market_cycles.py
    .\\.venv\\Scripts\\python.exe scripts\\label_market_cycles.py --reading B
    .\\.venv\\Scripts\\python.exe scripts\\label_market_cycles.py --from 2022-01-01

Reads only `data/history/nifty/1d/all.parquet` and, when present,
`data/history/vix/`. Writes nothing anywhere unless `--out` is given.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# His window. The market before and after Corona are different markets.
HIS_WINDOW_START = date(2022, 1, 1)

# His numbers, not tuned ones.
MIN_CYCLE_DAYS = 5          # "at least five trading days, one week, to count"
EXTREME_LOOKBACK = 10       # "no new 10-day high or low"
SHORT_RANGE_DAYS = 5        # "the last five to ten days"
BAND_DAYS = 10
LONG_RANGE_DAYS = 20        # "the 20-day average"

# How flat is flat. A sideways stretch must not be quietly drifting: the net move
# over the band window has to be small against the band it moved inside.
SIDEWAYS_NET_SHARE = 0.5

LABELS = [
    "SQUEEZE",
    "EXPANDING",
    "TRENDING UP",
    "TRENDING DOWN",
]


def load_daily(root: Path, start: date, end: date) -> pd.DataFrame:
    path = root / "nifty" / "1d" / "all.parquet"
    if not path.exists():
        raise SystemExit(
            f"Cannot find {path}. Run scripts/load_nifty_history.py --what 1d first."
        )
    frame = pd.read_parquet(path)
    frame["session"] = (
        pd.to_datetime(frame["bar_start_utc"], utc=True)
        .dt.tz_convert("Asia/Kolkata")
        .dt.date
    )
    frame = frame[(frame["session"] >= start) & (frame["session"] <= end)]
    frame = frame.sort_values("session").reset_index(drop=True)
    # 2019 and 2021 carry 406 bars with a high below their low, all zero volume,
    # a defect in FYERS' archive (PLAN 2.15.8). Drop them from a cycle study
    # rather than repairing another system's data.
    broken = frame["high"] < frame["low"]
    if broken.any():
        print(f"  note: {int(broken.sum())} bars have a high below their low; excluded.")
        frame = frame[~broken].reset_index(drop=True)
    return frame


def load_vix(root: Path) -> pd.DataFrame | None:
    """NSE's official daily VIX if it is on disk, else FYERS', else nothing."""
    nse = root / "vix" / "nse_daily" / "all.parquet"
    if nse.exists():
        frame = pd.read_parquet(nse)
        frame["session"] = pd.to_datetime(frame["trade_date"]).dt.date
        frame = frame[["session", "close"]].rename(columns={"close": "vix"})
        frame.attrs["source"] = "NSE official daily"
        return frame
    fyers = root / "vix" / "1d" / "all.parquet"
    if fyers.exists():
        frame = pd.read_parquet(fyers)
        frame["session"] = (
            pd.to_datetime(frame["bar_start_utc"], utc=True)
            .dt.tz_convert("Asia/Kolkata")
            .dt.date
        )
        frame = frame[["session", "close"]].rename(columns={"close": "vix"})
        frame.attrs["source"] = "FYERS daily"
        return frame
    return None


def measure(frame: pd.DataFrame) -> pd.DataFrame:
    """Adds every measurement his definitions need. No labelling yet."""
    out = frame.copy()
    out["day_range"] = out["high"] - out["low"]

    # Reading A: candle size now against candle size lately.
    out["range_short"] = out["day_range"].rolling(SHORT_RANGE_DAYS).mean()
    out["range_long"] = out["day_range"].rolling(LONG_RANGE_DAYS).mean()
    out["contraction_a"] = out["range_short"] / out["range_long"]

    # Reading B: the territory the last 10 days covered, against its own norm.
    band = (
        out["high"].rolling(BAND_DAYS).max() - out["low"].rolling(BAND_DAYS).min()
    )
    out["band_10"] = band
    out["band_norm"] = band.rolling(LONG_RANGE_DAYS).mean()
    out["contraction_b"] = band / out["band_norm"]

    # "No new 10-day high or low": today did not extend the last ten days either way.
    prior_high = out["high"].shift(1).rolling(EXTREME_LOOKBACK).max()
    prior_low = out["low"].shift(1).rolling(EXTREME_LOOKBACK).min()
    out["new_high"] = out["high"] > prior_high
    out["new_low"] = out["low"] < prior_low
    out["inside_band"] = ~(out["new_high"] | out["new_low"])

    # Direction, and how hard. Net move over the band window, in units of a
    # normal day's range, is the trend-strength measure the aggressive/basic
    # split will eventually use.
    out["net_move"] = out["close"] - out["close"].shift(BAND_DAYS)
    out["trend_strength"] = out["net_move"].abs() / (out["range_long"] * BAND_DAYS)
    out["net_share_of_band"] = out["net_move"].abs() / out["band_10"]
    return out


def label(out: pd.DataFrame, reading: str) -> pd.Series:
    """One raw label a day, before the five-day minimum is enforced."""
    contraction = out["contraction_a"] if reading == "A" else out["contraction_b"]
    contracting = contraction < 1.0
    expanding = contraction >= 1.0
    flat = out["net_share_of_band"] < SIDEWAYS_NET_SHARE

    raw = pd.Series(pd.NA, index=out.index, dtype="object")
    # His rule: the first two conditions define a squeeze. Nothing else may.
    raw[contracting & out["inside_band"]] = "SQUEEZE"
    # Sideways but widening, not contracting: expanding both ways.
    raw[raw.isna() & expanding & out["inside_band"] & flat] = "EXPANDING"
    # Everything left is going somewhere. The daily chart gives the direction.
    going = raw.isna() & out["net_move"].notna()
    raw[going & (out["net_move"] > 0)] = "TRENDING UP"
    raw[going & (out["net_move"] <= 0)] = "TRENDING DOWN"
    return raw


def enforce_minimum(raw: pd.Series, minimum: int = MIN_CYCLE_DAYS) -> pd.Series:
    """A stretch shorter than his five days is a pause, not a cycle.

    Short runs are absorbed into whichever neighbour is longer, repeatedly, until
    every surviving run is at least five sessions. This is his rule applied, not
    a smoothing parameter: "three sideways days inside a two-month uptrend are a
    pause inside the trend, not a cycle."
    """
    labels = raw.copy()
    valid = labels.notna()
    if not valid.any():
        return labels

    while True:
        runs: list[tuple[int, int, object]] = []
        start = None
        for i in labels.index:
            if pd.isna(labels[i]):
                continue
            if start is None or labels[i] != labels[start]:
                if start is not None:
                    runs.append((start, prev, labels[start]))
                start = i
            prev = i
        if start is not None:
            runs.append((start, prev, labels[start]))

        short = [r for r in runs if _run_length(labels, r[0], r[1]) < minimum]
        if not short or len(runs) <= 1:
            break

        # Fix the shortest run first so a chain of short runs resolves sensibly.
        short.sort(key=lambda r: _run_length(labels, r[0], r[1]))
        s0, s1, _ = short[0]
        position = next(i for i, r in enumerate(runs) if r[0] == s0)
        before = runs[position - 1] if position > 0 else None
        after = runs[position + 1] if position + 1 < len(runs) else None
        if before and after:
            take = (
                before
                if _run_length(labels, *before[:2]) >= _run_length(labels, *after[:2])
                else after
            )
        else:
            take = before or after
        if take is None:
            break
        labels.loc[s0:s1] = take[2]

    return labels


def _run_length(labels: pd.Series, start, end) -> int:
    return int(labels.loc[start:end].shape[0])


def runs_of(labels: pd.Series, sessions: pd.Series) -> pd.DataFrame:
    """Every labelled stretch as one row: label, first day, last day, length."""
    rows = []
    start = None
    prev = None
    for i in labels.index:
        if pd.isna(labels[i]):
            continue
        if start is None or labels[i] != labels[start]:
            if start is not None:
                rows.append((labels[start], sessions[start], sessions[prev],
                             int(prev - start + 1)))
            start = i
        prev = i
    if start is not None:
        rows.append((labels[start], sessions[start], sessions[prev],
                     int(prev - start + 1)))
    return pd.DataFrame(rows, columns=["label", "first", "last", "sessions"])


def report(out: pd.DataFrame, labels: pd.Series, reading: str,
           vix: pd.DataFrame | None) -> None:
    sessions = out["session"]
    labelled = labels.notna()
    total = int(labelled.sum())

    print()
    print("=" * 74)
    print(f"HIS CYCLES ON THE DAILY CHART, READING {reading}")
    print(f"{sessions.iloc[0]} to {sessions.iloc[-1]}, {len(out)} sessions, "
          f"{total} labelled")
    print("=" * 74)

    print("\nHOW OFTEN EACH APPEARS, by session")
    counts = labels.value_counts()
    for name in LABELS:
        n = int(counts.get(name, 0))
        print(f"  {name:15s} {n:5d} sessions   {100 * n / total:5.1f}%")
    unlabelled = len(out) - total
    if unlabelled:
        print(f"  {'(warm-up)':15s} {unlabelled:5d} sessions   "
              f"the first 20 days have no 20-day average yet")

    table = runs_of(labels, sessions)
    print(f"\nHOW LONG EACH LASTS, across {len(table)} stretches")
    print("  cycle            times   median   mean    longest   shortest")
    for name in LABELS:
        part = table[table["label"] == name]
        if part.empty:
            print(f"  {name:15s} {0:5d}   never appears")
            continue
        print(
            f"  {name:15s} {len(part):5d}   "
            f"{part['sessions'].median():6.1f}  {part['sessions'].mean():6.1f}   "
            f"{part['sessions'].max():7d}   {part['sessions'].min():8d}"
        )

    print("\nWHAT TENDED TO FOLLOW, as a share of each cycle's endings")
    nxt = table["label"].shift(-1)
    for name in LABELS:
        mask = (table["label"] == name) & nxt.notna()
        if not mask.any():
            continue
        follow = nxt[mask].value_counts(normalize=True)
        parts = ", ".join(f"{k} {100 * v:.0f}%" for k, v in follow.items())
        print(f"  after {name:15s} -> {parts}")

    print("\nWHAT THE INDEX DID NEXT, median move over the 10 sessions after a "
          "stretch ends")
    closes = out["close"].reset_index(drop=True)
    idx_by_session = {s: i for i, s in enumerate(sessions)}
    for name in LABELS:
        part = table[table["label"] == name]
        moves = []
        for _, row in part.iterrows():
            i = idx_by_session.get(row["last"])
            if i is None or i + 10 >= len(closes):
                continue
            moves.append(100 * (closes[i + 10] - closes[i]) / closes[i])
        if moves:
            arr = np.array(moves)
            print(f"  after {name:15s} median {np.median(arr):+6.2f}%   "
                  f"up {100 * (arr > 0).mean():4.0f}% of the time   n={len(arr)}")
        else:
            print(f"  after {name:15s} not enough history to say")

    if vix is not None:
        merged = pd.DataFrame({"session": sessions, "label": labels}).merge(
            vix, on="session", how="left"
        )
        have = merged["vix"].notna().sum()
        print(f"\nHIS THIRD CONDITION, THE VIX CONFIRMATION "
              f"({vix.attrs.get('source', 'unknown source')}, "
              f"{have} of {len(merged)} sessions matched)")
        if have:
            median_all = merged["vix"].median()
            for name in LABELS:
                part = merged[merged["label"] == name]["vix"].dropna()
                if part.empty:
                    continue
                print(f"  {name:15s} median VIX {part.median():6.2f}   "
                      f"below the period median {100 * (part < median_all).mean():4.0f}% "
                      f"of the time")
            print(f"  period median VIX {median_all:.2f}. His rule is that the VIX")
            print("  CONFIRMS a squeeze rather than defining it, so this column is a")
            print("  check on the definition, never part of it.")
    else:
        print("\nHIS THIRD CONDITION, THE VIX: no VIX file on disk yet, so the")
        print("  confirmation is unmeasured. Run scripts/load_india_vix.py.")

    print("\nTHE AGGRESSIVE AGAINST BASIC SPLIT, WHICH IS STILL HIS TO SET")
    trending = labels.isin(["TRENDING UP", "TRENDING DOWN"])
    strength = out.loc[trending, "trend_strength"].dropna()
    if len(strength):
        qs = strength.quantile([0.25, 0.5, 0.75, 0.9]).round(3)
        print("  Trend strength is the net 10-day move divided by ten normal days'")
        print("  range. 1.00 would mean every day moved its full range one way.")
        for q, v in qs.items():
            print(f"    {int(q * 100):>3d}th percentile  {v}")
        print(f"  PLACEHOLDER, not his number: splitting at the median "
              f"{strength.median():.3f} would")
        print("  call half of his trending days aggressive. He has to choose the line.")

    print("\nTHE FIVE LONGEST STRETCHES OF EACH, so he can put them on his chart")
    for name in LABELS:
        part = table[table["label"] == name].nlargest(5, "sessions")
        if part.empty:
            continue
        print(f"  {name}")
        for _, row in part.iterrows():
            print(f"    {row['first']} to {row['last']}  {row['sessions']:3d} sessions")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="Defaults to data/history.")
    parser.add_argument("--from", dest="start", help="YYYY-MM-DD. Defaults to 2022-01-01.")
    parser.add_argument("--to", dest="end", help="YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--reading", choices=["A", "B", "both"], default="both")
    parser.add_argument("--out", help="Optional CSV of the day-by-day labels.")
    args = parser.parse_args()

    root = Path(args.root) if args.root else ROOT_DIR / "data" / "history"
    start = date.fromisoformat(args.start) if args.start else HIS_WINDOW_START
    end = date.fromisoformat(args.end) if args.end else date.today()

    print(f"Reading NIFTY daily bars from {root}")
    daily = load_daily(root, start, end)
    out = measure(daily)
    vix = load_vix(root)

    readings = ["A", "B"] if args.reading == "both" else [args.reading]
    last = None
    for reading in readings:
        labels = enforce_minimum(label(out, reading))
        report(out, labels, reading, vix)
        last = labels

    if args.out and last is not None:
        frame = pd.DataFrame({"session": out["session"], "cycle": last})
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.out, index=False)
        print(f"\nDay-by-day labels written to {args.out}")

    print("\nNothing was built. This script measures his definitions and reports.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
