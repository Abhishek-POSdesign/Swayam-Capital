"""
Trade Journal Markdown writer for Swayam Capital.

Generates structured, YAML-frontmattered Obsidian markdown notes for executed trades
in Abhishek's Second Brain under `02 - Projects/Trading/04 - Journal/`.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Optional
from swayam.config import settings


class JournalWriteError(Exception):
    """Raised when writing the trade journal fails or attempts an unsafe overwrite."""
    pass


def _charge_cell(value: Optional[float], *, signed: bool = False) -> str:
    """A rupee figure for a table cell, or an em dash when nothing is known.

    A leg opened before charges were recorded per leg carries no entry cost.
    That is a gap, and a gap prints as a dash rather than as zero rupees.
    """
    if value is None:
        return "—"
    amount = float(value)
    if signed:
        sign = "+" if amount > 0 else ""
        return f"{sign}₹{amount:,.2f}"
    return f"₹{amount:,.2f}"

def _default_vault_base() -> Path:
    """The vault every write lands in when the caller names no other.

    WHY THIS IS NOT SIMPLY `settings.vault_path`
    --------------------------------------------
    On 2026-09-08 twenty-six fabricated trade notes were found in Abhishek's
    real trade journal folder, `02 - Projects/Trading/04 - Journal/`. Only four
    of them had a matching row in the database; the other twenty-two existed
    nowhere but his Second Brain. They were written by test runs.

    `tests/db_guard.py` cages the database. Nothing caged the vault, and every
    writer here fell back to the live path when no override was passed, so any
    test that exercised `/api/execute` end to end wrote a real file into his
    record. The vault is the thing this project exists to protect, so the cage
    now covers it too.

    Reads are untouched: the AI persona still reads his Method files from the
    real vault. Only writes are gated, and only while a test is running.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        raise JournalWriteError(
            "BLOCKED: a test tried to write into the live Obsidian vault at "
            f"{settings.vault_path}. Tests must pass an explicit `vault_path`, "
            "or rely on the autouse `cage_the_vault` fixture in tests/conftest.py "
            "which redirects writes to a temporary folder. Twenty-six fabricated "
            "trades reached his real journal this way on 2026-09-08."
        )
    return settings.vault_path


def _greek(greeks: dict, key: str, spec: str, *, prefix: str = "", suffix: str = "") -> str:
    """A Greek, or an em dash. Never a zero he never measured.

    A missing Greek used to render as 0.0000, which on a real trade note reads
    as a measured neutral position. A note rebuilt from the database has no
    Greeks stored, and that must say so.
    """
    value = greeks.get(key)
    if value is None:
        return "—"
    return f"{prefix}{float(value):{spec}}{suffix}"


def _require_reachable_vault(base: Path) -> Path:
    """His vault, or a refusal. NEVER a folder invented inside a container.

    WHAT WENT WRONG, 2026-09-09, on his first ever paper trade.
    ---------------------------------------------------------
    `VAULT_PATH` is unset on Cloud Run, so `config.py` falls back to the Windows
    path for his G: drive. On Linux that is not a drive at all: it is
    a RELATIVE folder whose name happens to contain a colon and backslashes.
    `get_journal_dir` then called `mkdir(parents=True, exist_ok=True)`, which
    cheerfully created it inside the container. The write succeeded, the row was
    marked `journal_status = 'written'`, and the note died with the container.

    His trade note for 2026-09-09 was reported as written and was never in his
    vault. That is a false claim on his record, which is the one thing this
    project exists to prevent.

    The outbox already exists for exactly this case: a note that cannot be
    written is queued and the drainer completes it from his PC, where the vault
    is real. It was never reached because nothing ever failed.

    So the base must ALREADY EXIST as a directory. We create the journal folder
    inside a real vault; we never create the vault.
    """
    if not base.is_dir():
        raise JournalWriteError(
            f"The vault is not reachable at {base}, so this note cannot be "
            "written. On Cloud Run that is expected: the container cannot see "
            "his G: drive. Queue the note in swayam_journal_outbox and let "
            "scripts/drain_journal_outbox.py complete it from his PC. It must "
            "NEVER be written into the container, which is what used to happen."
        )
    return base


# Notes written before he says paper trading has begun go in their own room.
TERMINAL_TESTS_SUBFOLDER = "Terminal tests"


def journal_rel_dir(terminal_test: bool = False) -> str:
    """The vault-relative folder a note of this kind belongs in."""
    base = "02 - Projects/Trading/04 - Journal"
    return f"{base}/{TERMINAL_TESTS_SUBFOLDER}" if terminal_test else base


def get_journal_dir(vault_path: Optional[Path] = None, terminal_test: bool = False) -> Path:
    """The folder this note belongs in, created inside a vault that already exists.

    `terminal_test` puts the note in `04 - Journal/Terminal tests/` instead of
    the journal folder itself. His correction of 2026-09-10: everything the
    terminal has recorded so far was a click to see how it behaves, not a trade
    he planned, and his paper record has to start clean on the day he says.

    THE PHASE IS PASSED IN, NOT READ HERE, on purpose. This module writes files
    into his Second Brain and nothing else; giving it a database read of its own
    would put a network call inside the one code path that must never surprise
    anybody. The callers that open trades already read the phase for the
    position's `provenance`, and they hand the same answer down here, so the row
    and the note can never disagree about what a trade was.
    """
    base = _require_reachable_vault(vault_path or _default_vault_base())
    journal_dir = base / "02 - Projects" / "Trading" / "04 - Journal"
    if terminal_test:
        journal_dir = journal_dir / TERMINAL_TESTS_SUBFOLDER
    journal_dir.mkdir(parents=True, exist_ok=True)
    return journal_dir


def determine_next_trade_sequence(journal_dir: Path, trade_date_str: str) -> str:
    """Calculates the 2-digit zero-padded sequence number for trades on a given date.

    Args:
        journal_dir: Path to the journal folder.
        trade_date_str: Date string in YYYY-MM-DD format.

    Returns:
        str: Two-digit sequence, e.g. "01", "02".
    """
    prefix = f"{trade_date_str}-trade"
    existing = [f.name for f in journal_dir.glob(f"{prefix}*.md")]
    next_idx = len(existing) + 1
    return f"{next_idx:02d}"


def write_new_trade_journal(
    position_id: str,
    spread_data: dict[str, Any],
    validation_data: dict[str, Any],
    current_spot: float,
    margin_base_inr: float,
    vault_path: Optional[Path] = None,
    filename_override: Optional[str] = None,
    notice: Optional[str] = None,
    opened_at: Optional[str] = None,
    terminal_test: bool = False,
) -> str:
    """Writes a new trade journal markdown note to Obsidian Second Brain.

    `opened_at` is when the TRADE opened, as recorded on the position. The
    note used to stamp "Time opened" with the moment the note was written,
    so trades 02 and 03 of 2026-09-09 say they opened at 16:57, after the
    close, because that is when the drainer ran. A fabricated timestamp in his
    record. When it is absent the note says so rather than pretending.

    `filename_override` writes to an exact filename instead of the next number
    in the day's sequence. It exists so a note that was recorded in the database
    but never reached the vault can be rebuilt under the name the database
    already points at, rather than under a new one that nothing references.

    `notice` puts a line at the top of the note. Used to say, on the face of the
    note, that it was rebuilt and what could not be recovered.

    Args:
        position_id: Unique UUID or string identifying the position.
        spread_data: Dictionary containing strategy_name, underlying, legs,
                     payoff_curve, and greeks.
        validation_data: Dictionary containing validation checks and verdict.
        current_spot: Underlying spot price at entry.
        margin_base_inr: Current margin base in rupees.
        vault_path: Optional override for test isolation.

    Returns:
        str: Relative path within vault (e.g. '02 - Projects/Trading/04 - Journal/2026-09-04-trade01.md').

    Raises:
        JournalWriteError: If target file already exists or write fails.
    """
    journal_dir = get_journal_dir(vault_path, terminal_test=terminal_test)
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    if filename_override:
        filename = filename_override
        stem = filename_override.rsplit(".", 1)[0]
        seq_str = stem.rsplit("trade", 1)[-1] if "trade" in stem else "01"
        date_str = stem.split("-trade")[0] if "-trade" in stem else date_str
    else:
        seq_str = determine_next_trade_sequence(journal_dir, date_str)
        filename = f"{date_str}-trade{seq_str}.md"
    target_path = journal_dir / filename

    if target_path.exists():
        raise JournalWriteError(f"Target journal file already exists: {target_path}. Overwrite prevented.")

    strategy_name = spread_data.get("strategy_name", "Options Strategy")
    underlying = spread_data.get("underlying", "NIFTY")
    legs = spread_data.get("legs", [])
    payoff = spread_data.get("payoff_curve", {})
    greeks = spread_data.get("greeks", {})
    notice_block = f"\n> **{notice}**\n" if notice else ""

    # UNLIMITED IS NOT ZERO. A net short call has no worst case at expiry, and
    # the row stores NULL for it. Printing "Max loss: Rs 0" into his permanent
    # record would be the most reassuring lie this terminal could tell.
    _raw_max_loss = payoff.get("max_loss_inr")
    max_loss_inr = None if _raw_max_loss is None else float(_raw_max_loss)
    max_loss_unbounded = payoff.get("max_loss_unbounded_reason")
    max_profit_inr = float(payoff.get("max_profit_inr", 0.0))
    # THE SAME TRAP AS THE MAXIMUM LOSS. There is no reward-to-risk ratio when
    # the risk has no ceiling, so this is None, and the key is present so a
    # default would never have fired.
    _raw_rr = payoff.get("rr_implied")
    rr_implied = None if _raw_rr is None else float(_raw_rr)
    rr_text = "unavailable, the risk has no ceiling" if rr_implied is None else f"{rr_implied:.2f}"
    net_debit_credit = float(payoff.get("net_debit_credit_inr", 0.0))
    breakevens = payoff.get("breakevens", [])
    expiry_date = legs[0].get("expiry_date", date_str) if legs else date_str

    # A percentage of nothing is not 0.00%, it is unknown. Trade 01's rebuilt
    # note printed "0.00% of margin base" because the rebuild passed no balance.
    max_loss_pct_text = (
        f"{max_loss_inr / margin_base_inr * 100.0:.2f}% of margin base"
        if max_loss_inr is not None and margin_base_inr and margin_base_inr > 0
        else "% of margin base unavailable, no balance was read"
    )
    # The one line the note prints. Unlimited says so in words and carries the
    # reason; a bounded loss reads exactly as it always did.
    if max_loss_inr is None:
        max_loss_text = (
            f"**UNLIMITED** — {max_loss_unbounded}"
            if max_loss_unbounded
            else "**UNLIMITED** — this structure has no worst case at expiry"
        )
    else:
        max_loss_text = f"₹{max_loss_inr:,.0f} ({max_loss_pct_text})"
    opened_text = _ist_stamp(opened_at) if opened_at else f"{now.isoformat()} (the note's time; the trade's was not recorded)"
    margin_required = spread_data.get("margin_required_inr")
    margin_line = (
        f"- **Margin the broker needed**: ₹{float(margin_required):,.0f}\n"
        if margin_required is not None
        else "- **Margin the broker needed**: unavailable at entry\n"
    )
    fill_basis = spread_data.get("fill_basis")
    fill_line = (
        "- **Fills**: buy at the ask, sell at the bid\n" if fill_basis == "bid_ask"
        else "- **Fills**: at the traded price. Not comparable with trades filled at the bid and ask.\n" if fill_basis == "traded_price"
        else ""
    )
    # Legs booked through the execution ticket carry how they were filled.
    # Older legs do not, and the older table shape is kept for them.
    ticketed = any(leg.get("order_type") or leg.get("ltp_at_fill") is not None for leg in legs)

    # Build legs table rows
    leg_rows = []
    for idx, leg in enumerate(legs, start=1):
        if ticketed:
            ltp = leg.get("ltp_at_fill")
            leg_rows.append(
                f"| {idx} | {leg.get('strike'):,.0f} | {leg.get('option_type')} | "
                f"{leg.get('direction', '').upper()} | {leg.get('quantity_lots', 1)} | "
                f"{str(leg.get('order_type') or '—').lower()} | "
                f"₹{float(leg.get('entry_premium', 0.0)):,.2f} | "
                f"{('₹' + format(float(ltp), ',.2f')) if ltp is not None else '—'} | "
                f"{_charge_cell(leg.get('entry_charges_inr'))} |"
            )
        else:
            leg_rows.append(
                f"| {idx} | {leg.get('strike'):,.0f} | {leg.get('option_type')} | "
                f"{leg.get('direction', '').upper()} | {leg.get('quantity_lots', 1)} | "
                f"₹{float(leg.get('entry_premium', 0.0)):,.2f} | "
                f"{_charge_cell(leg.get('entry_charges_inr'))} |"
            )
    legs_table = "\n".join(leg_rows)
    legs_header = (
        "| # | Strike | Type | Direction | Lots | Order | Fill | Traded | Charges |\n"
        "|:---:|---:|:---:|:---:|:---:|:---:|---:|---:|---:|"
        if ticketed
        else "| # | Strike | Type | Direction | Lots | Entry Premium | Charges |\n"
        "|:---:|---:|:---:|:---:|:---:|---:|---:|"
    )

    # Build validation checks bullets
    val_bullets = []
    for check in validation_data.get("checks", []):
        icon = "✅" if check.get("verdict") == "PASS" else "❌"
        rule_name = check.get("rule", "").replace("_", " ").title()
        note = check.get("note", "")
        if check.get("actual_inr") is not None and check.get("cap_inr") is not None:
            detail = f"₹{check['actual_inr']:,.0f} ≤ ₹{check['cap_inr']:,.0f}"
        elif check.get("actual") is not None and check.get("floor") is not None:
            detail = f"{check['actual']:.2f} ≥ {check['floor']:.2f}"
        else:
            detail = note
        val_bullets.append(f"- {icon} **{rule_name}**: {detail}")
    validation_text = "\n".join(val_bullets) if val_bullets else "- ✅ All Method rule checks passed."

    breakeven_str = ", ".join([f"{b:,.0f}" for b in breakevens]) if breakevens else "None"

    # WHAT THIS TRADE WAS, on the face of the note. A terminal test is a real
    # fill with real charges that he took to see how the terminal behaves, and
    # it does not belong in the record his paper results are judged against.
    provenance_value = "terminal_test" if terminal_test else "live"

    content = f"""---
trade_id: {position_id}
date: {date_str}
strategy: {strategy_name}
underlying: {underlying}
status: open
mode: paper
provenance: {provenance_value}
---

# {date_str} — Trade #{seq_str} — {strategy_name}
{notice_block}

## Entry (paper trade)

- **Time opened**: {opened_text}
- **NIFTY spot at entry**: {current_spot:,.2f}
- **Underlying**: {underlying}
- **Expiry**: {expiry_date}
{margin_line}{fill_line}
### Legs

{legs_header}
{legs_table}

### Risk / Reward

- **Max loss**: {max_loss_text}
- **Max profit**: ₹{max_profit_inr:,.0f}
- **R:R implied**: {rr_text}
- **Net debit/credit**: ₹{net_debit_credit:,.0f}
- **Breakeven(s)**: {breakeven_str}

### Greeks at entry

- Net Delta: {_greek(greeks, 'net_delta', '.4f')}
- Net Theta: {_greek(greeks, 'net_theta_per_day', '.0f', prefix='₹', suffix='/day')}
- Net Vega: {_greek(greeks, 'net_vega', '.0f', prefix='₹', suffix=' per 1% IV')}
- Net Gamma: {_greek(greeks, 'net_gamma', '.6f')}

### Method rule validation

{validation_text}

### Entry rationale (fill in manually)

*Why this trade, why now, what setup, what invalidates it. Written by Abhishek after the fact.*

---

## Daily updates

*Add one section per day the trade is open — what the trade is doing, how it's performing, what you're thinking, should you exit, should you add.*

---

## Exit (to be filled at close)

- **Time closed**: TBD
- **Exit price**: TBD
- **P&L realized**: TBD
- **What went right**: TBD
- **What went wrong**: TBD
- **What I learned**: TBD
"""

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        raise JournalWriteError(f"Failed to write journal to {target_path}: {e}") from e

    rel_path = f"{journal_rel_dir(terminal_test)}/{filename}"
    return rel_path


def _ist_stamp(iso: str) -> str:
    """An ISO timestamp as he reads it: IST, to the second."""
    try:
        from datetime import timedelta
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ist = dt.astimezone(timezone(timedelta(hours=5, minutes=30)))
        return f"{ist:%Y-%m-%d %H:%M:%S} IST"
    except Exception:
        return str(iso)


def append_leg_block(
    journal_rel_path: str,
    added_at: str,
    leg: dict[str, Any],
    structure_after: dict[str, Any],
    vault_path: Optional[Path] = None,
) -> Path:
    """Records a leg added to an open trade, under an Adjustments heading.

    His own sheet has "Initial Position Legs", then "Trade Adjustments", then
    "Booked Orders / Exits". This is the middle one. The block sits between
    the entry and the exit so the note reads in the order the trade happened.
    """
    base_vault = _require_reachable_vault(vault_path or _default_vault_base())
    target_path = base_vault / journal_rel_path
    if not target_path.exists():
        raise JournalWriteError(f"Target journal file does not exist: {target_path}")
    content = target_path.read_text(encoding="utf-8")

    ltp = leg.get("ltp_at_fill")
    row = (
        f"| {leg.get('sequence', '—')} | {float(leg.get('strike', 0)):,.0f} | {leg.get('option_type')} | "
        f"{str(leg.get('direction', '')).upper()} | {leg.get('quantity_lots', 1)} | "
        f"{str(leg.get('order_type') or '—').lower()} | ₹{float(leg.get('entry_premium', 0.0)):,.2f} | "
        f"{('₹' + format(float(ltp), ',.2f')) if ltp is not None else '—'} | "
        f"{_charge_cell(leg.get('entry_charges_inr'))} |"
    )
    bes = structure_after.get("breakevens") or []
    be_text = ", ".join(f"{float(b):,.0f}" for b in bes) if bes else "none"
    margin = structure_after.get("margin_required_inr")
    block = f"""### Leg added — {_ist_stamp(added_at)}

| # | Strike | Type | Direction | Lots | Order | Fill | Traded | Charges |
|:---:|---:|:---:|:---:|:---:|:---:|---:|---:|---:|
{row}

The trade now holds {structure_after.get('legs_count', '—')} legs. Net debit/credit ₹{float(structure_after.get('net_debit_credit_inr') or 0):,.0f}, max loss {('unlimited' if structure_after.get('max_loss_inr') is None else '₹' + format(float(structure_after['max_loss_inr']), ',.0f'))}, max profit ₹{float(structure_after.get('max_profit_inr') or 0):,.0f}, breakeven(s) {be_text}, broker margin {('₹' + format(float(margin), ',.0f')) if margin is not None else 'unavailable'}.

"""
    heading = "## Adjustments"
    exit_idx = content.find("\n## Exit")
    if exit_idx == -1:
        content = content.rstrip() + "\n\n---\n\n" + (heading + "\n\n" if heading not in content else "") + block
    elif heading in content:
        content = content[:exit_idx] + "\n" + block + content[exit_idx:].lstrip("\n")
    else:
        content = content[:exit_idx] + "\n" + heading + "\n\n" + block + "---\n" + content[exit_idx:].lstrip("\n")

    try:
        target_path.write_text(content, encoding="utf-8")
    except Exception as e:
        raise JournalWriteError(f"Failed to append leg block to {target_path}: {e}") from e
    return target_path


def append_leg_exit_block(
    journal_rel_path: str,
    closed_at: str,
    leg: dict[str, Any],
    close_reason: Optional[str] = None,
    notes: Optional[str] = None,
    opened_leg: Optional[dict[str, Any]] = None,
    structure_after: Optional[dict[str, Any]] = None,
    vault_path: Optional[Path] = None,
) -> Path:
    """Records ONE leg squared off inside a trade that is still running.

    His own sheet has "Initial Position Legs", then "Trade Adjustments", then
    "Booked Orders / Exits", often on different days. A leg exited on its own
    is the middle one, not the last: the trade is not closed and must not get
    an Exit block, which is what the record reads as squared off.

    A reverse writes the same block with the opposite leg named beneath it,
    because it is one decision and reads as one.
    """
    base_vault = _require_reachable_vault(vault_path or _default_vault_base())
    target_path = base_vault / journal_rel_path
    if not target_path.exists():
        raise JournalWriteError(f"Target journal file does not exist: {target_path}")
    content = target_path.read_text(encoding="utf-8")

    contracts = int(leg.get("quantity_lots", 1) or 1) * int(leg.get("lot_size", 0) or 0)
    exit_ltp = leg.get("exit_ltp")
    net = leg.get("net_pnl_inr")
    gross = leg.get("gross_pnl_inr")
    side_hit = leg.get("exit_side_hit") or "—"

    row = (
        f"| {leg.get('sequence', '—')} | {float(leg.get('strike', 0)):,.0f} | {leg.get('option_type')} | "
        f"{str(leg.get('direction', '')).upper()} | {leg.get('quantity_lots', 1)} | "
        f"{str(leg.get('exit_order_type') or '—').lower()} | "
        f"₹{float(leg.get('entry_premium', 0.0)):,.2f} | "
        f"₹{float(leg.get('exit_premium', 0.0)):,.2f} | {side_hit} | "
        f"{('₹' + format(float(exit_ltp), ',.2f')) if exit_ltp is not None else '—'} | "
        f"{_charge_cell(leg.get('exit_charges_inr'))} | "
        f"{_charge_cell(gross, signed=True)} | {_charge_cell(net, signed=True)} |"
    )

    opened_line = ""
    if opened_leg:
        opened_line = (
            f"\nReversed: {str(opened_leg.get('direction', '')).upper()} "
            f"{float(opened_leg.get('strike', 0)):,.0f} {opened_leg.get('option_type')} "
            f"opened at ₹{float(opened_leg.get('entry_premium', 0.0)):,.2f} "
            f"on the {opened_leg.get('side_hit') or '—'}, "
            f"charges {_charge_cell(opened_leg.get('entry_charges_inr'))}, "
            f"as leg {opened_leg.get('sequence', '—')} of the same trade.\n"
        )

    after = structure_after or {}
    if after.get("all_closed"):
        holding_line = "Every leg is now closed, so the trade is closed and its result is in the record."
    else:
        bes = after.get("breakevens") or []
        be_text = ", ".join(f"{float(b):,.0f}" for b in bes) if bes else "none"
        margin = after.get("margin_required_inr")
        holding_line = (
            f"The trade stays open with {after.get('legs_count', '—')} leg(s). "
            f"Max loss {('unlimited' if after.get('max_loss_inr') is None else '₹' + format(float(after['max_loss_inr']), ',.0f'))}, "
            f"max profit ₹{float(after.get('max_profit_inr') or 0):,.0f}, "
            f"breakeven(s) {be_text}, broker margin "
            f"{('₹' + format(float(margin), ',.0f')) if margin is not None else 'unavailable'}."
        )

    reason_line = f"Reason: {close_reason}." if close_reason else ""
    note_line = f"\n\n> {notes}" if notes else ""

    block = f"""### Leg squared off — {_ist_stamp(closed_at)}

| # | Strike | Type | Held | Lots | Order | Entry | Exit | Side | Traded | Exit charges | Gross | Net |
|:---:|---:|:---:|:---:|:---:|:---:|---:|---:|:---:|---:|---:|---:|---:|
{row}

{contracts} units. {reason_line} {holding_line}{opened_line}{note_line}

"""

    heading = "## Adjustments"
    exit_idx = content.find("\n## Exit")
    if exit_idx == -1:
        content = content.rstrip() + "\n\n---\n\n" + (heading + "\n\n" if heading not in content else "") + block
    elif heading in content:
        content = content[:exit_idx] + "\n" + block + content[exit_idx:].lstrip("\n")
    else:
        content = content[:exit_idx] + "\n" + heading + "\n\n" + block + "---\n" + content[exit_idx:].lstrip("\n")

    try:
        target_path.write_text(content, encoding="utf-8")
    except Exception as e:
        raise JournalWriteError(f"Failed to append leg exit block to {target_path}: {e}") from e
    return target_path


def append_exit_block(
    journal_rel_path: str,
    closed_at: datetime,
    close_reason: str,
    notes: Optional[str],
    exit_legs: list[dict[str, Any]],
    gross_pnl_inr: float,
    charges_inr: float,
    net_pnl_inr: float,
    # NONE MEANS THE RISK HAD NO CEILING, not that it was zero. A naked trade
    # stores no maximum loss, and "% of max risk: 0.0%" against a risk of
    # nothing is a fabricated figure in his permanent record.
    max_loss_inr: Optional[float],
    margin_base_inr: float,
    holding_days: int,
    vault_path: Optional[Path] = None,
) -> Path:
    """Updates the Obsidian trade journal note with closing details and realized P&L.

    Updates the frontmatter status from 'open' to 'closed' and replaces the
    '## Exit (to be filled at close)' section with a structured exit report.

    Args:
        journal_rel_path: Relative path to the journal note within the vault.
        closed_at: Datetime of trade exit.
        close_reason: Trigger ('target_hit', 'stop_hit', 'time_exit', 'manual').
        notes: User reflection or exit rationale text.
        exit_legs: List of legs with strike, option_type, direction, exit_premium.
        gross_pnl_inr: Gross realized profit/loss before exchange charges.
        charges_inr: Estimated exchange/regulatory transaction costs.
        net_pnl_inr: Realized profit/loss after charges.
        max_loss_inr: Planned maximum risk at entry.
        margin_base_inr: Account margin base in rupees.
        holding_days: Number of days the position was held.
        vault_path: Optional override for vault path (e.g. during testing).

    Returns:
        Path: Absolute path to the modified journal note.

    Raises:
        JournalWriteError: If the file does not exist or write fails.
    """
    base_vault = _require_reachable_vault(vault_path or _default_vault_base())
    target_path = base_vault / journal_rel_path

    if not target_path.exists():
        raise JournalWriteError(f"Target journal file does not exist: {target_path}")

    try:
        content = target_path.read_text(encoding="utf-8")
    except Exception as e:
        raise JournalWriteError(f"Failed to read journal file {target_path}: {e}") from e

    closed_at_iso = closed_at.isoformat()

    # 1. Update YAML frontmatter
    # Replace 'status: open' with 'status: closed' and append closed_at, realized_pnl, close_reason
    if "status: open" in content:
        content = content.replace("status: open", "status: closed", 1)
        # Inject closing fields right before the closing ---
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            extra_fm = (
                f"\nclosed_at: {closed_at_iso}\n"
                f"realized_pnl_inr: {net_pnl_inr:.2f}\n"
                f"close_reason: {close_reason}"
            )
            content = f"---{frontmatter.rstrip()}{extra_fm}\n---{parts[2]}"

    # 2. Build Exit Legs Table. A leg closed through the book carries the side
    # it hit and the traded price beside it; older legs keep the older shape.
    booked = any(l.get("exit_side_hit") or l.get("exit_ltp") is not None for l in exit_legs)
    leg_rows = []
    for idx, leg in enumerate(exit_legs, start=1):
        strike = leg.get("strike", 0.0)
        opt_type = leg.get("option_type", "")
        # Close direction is opposite of entry
        entry_dir = leg.get("direction", "").upper()
        if entry_dir in ("BUY", "LONG"):
            exit_dir = "SELL"
        elif entry_dir in ("SELL", "SHORT"):
            exit_dir = "BUY"
        else:
            exit_dir = leg.get("exit_direction", "CLOSE").upper()

        prem = float(leg.get("exit_premium", 0.0))
        if booked:
            traded = leg.get("exit_ltp")
            leg_rows.append(
                f"| {idx} | {strike:,.0f} | {opt_type} | {exit_dir} | "
                f"{str(leg.get('exit_side_hit') or leg.get('exit_fill_basis') or '—')} | ₹{prem:,.2f} | "
                f"{('₹' + format(float(traded), ',.2f')) if traded is not None else '—'} | "
                f"{_charge_cell(leg.get('gross_pnl_inr'), signed=True)} | "
                f"{_charge_cell(leg.get('charges_inr'))} | "
                f"{_charge_cell(leg.get('net_pnl_inr'), signed=True)} |"
            )
        else:
            leg_rows.append(
                f"| {idx} | {strike:,.0f} | {opt_type} | {exit_dir} | ₹{prem:,.2f} | "
                f"{_charge_cell(leg.get('gross_pnl_inr'), signed=True)} | "
                f"{_charge_cell(leg.get('charges_inr'))} | "
                f"{_charge_cell(leg.get('net_pnl_inr'), signed=True)} |"
            )

    exit_legs_table = "\n".join(leg_rows) if leg_rows else "| 1 | — | — | CLOSE | — | — | — | — |"
    exit_legs_header = (
        "| # | Strike | Type | Direction | Side | Exit fill | Traded | Gross | Charges | Net |\n"
        "|:---:|---:|:---:|:---:|:---:|---:|---:|---:|---:|---:|"
        if booked
        else "| # | Strike | Type | Direction | Exit Premium | Gross | Charges | Net |\n"
        "|:---:|---:|:---:|:---:|---:|---:|---:|---:|"
    )
    fills_line = (
        "- **Exit fills**: sold at the bid, bought back at the ask\n"
        if booked and any(str(l.get("exit_fill_basis")) == "bid_ask" for l in exit_legs)
        else ""
    )

    # Risk metrics
    # A percentage of a risk that had no ceiling is not 0.0%, it is no answer.
    if max_loss_inr is None:
        pct_of_risk_text = "the risk had no ceiling, so there is no percentage of it"
    elif max_loss_inr > 0:
        pct_of_risk_text = f"{net_pnl_inr / max_loss_inr * 100.0:.1f}%"
    else:
        pct_of_risk_text = "unavailable, no maximum risk was recorded"
    pct_of_margin_text = (
        f"{net_pnl_inr / margin_base_inr * 100.0:.2f}%" if margin_base_inr and margin_base_inr > 0
        else "unavailable, no balance was read"
    )

    notes_text = notes.strip() if notes and notes.strip() else "(none)"

    exit_block = f"""## Exit

- **Time closed**: {closed_at_iso} ({holding_days} days held)
- **Close reason**: {close_reason}
- **Notes**: {notes_text}
{fills_line}
### Exit legs

{exit_legs_header}
{exit_legs_table}

### Realized P&L

- **Gross P&L**: ₹{gross_pnl_inr:,.0f}
- **Charges, entry and exit, summed from the legs**: ₹{charges_inr:,.2f}
- **NET realized P&L**: ₹{net_pnl_inr:,.0f}
- **% of max risk**: {pct_of_risk_text}
- **% of margin base**: {pct_of_margin_text}

### Post-trade reflection (fill in manually)

- **What went right**: TBD
- **What went wrong**: TBD
- **What I learned**: TBD
- **What I would do differently next time**: TBD

*Auto-populated by Swayam Capital on trade close. Reflection fields to be filled in manually.*
"""

    placeholder = "## Exit (to be filled at close)"
    if placeholder in content:
        # Replace the placeholder and anything below it
        idx = content.find(placeholder)
        content = content[:idx] + exit_block
    else:
        # Fallback: append at the end
        content = content.rstrip() + "\n\n---\n\n" + exit_block

    try:
        target_path.write_text(content, encoding="utf-8")
    except Exception as e:
        raise JournalWriteError(f"Failed to write updated exit block to {target_path}: {e}") from e

    return target_path


def append_or_update_lesson_block(
    journal_rel_path: str,
    lesson_text: str,
    lesson_source: str = "ai_generated",
    vault_path: Optional[Path] = None,
) -> Optional[Path]:
    """Appends or updates the ## Lesson block in an Obsidian trade note.

    Args:
        journal_rel_path: Relative path within vault (e.g. '02 - Projects/Trading/04 - Journal/2026-09-04-trade01.md').
        lesson_text: Single-sentence grounded lesson text.
        lesson_source: 'ai_generated', 'user_edited', or 'ai_failed'.
        vault_path: Optional vault path override for tests.

    Returns:
        Path to updated file or None if note not found.
    """
    base = _require_reachable_vault(vault_path or _default_vault_base())
    target_path = base / journal_rel_path
    if not target_path.exists():
        return None

    try:
        content = target_path.read_text(encoding="utf-8")
    except Exception:
        return None

    lesson_block = f"## Lesson\n\n> **Lesson ({lesson_source})**: {lesson_text}\n"

    if "## Lesson" in content:
        # Replace existing Lesson block
        parts = content.split("## Lesson")
        prefix = parts[0].rstrip()
        rest = parts[1]
        # Find if there is any subsequent ## heading
        next_heading_idx = -1
        lines = rest.splitlines()
        for idx_line, line in enumerate(lines):
            if idx_line > 0 and line.strip().startswith("## "):
                next_heading_idx = rest.find(line)
                break
        suffix = rest[next_heading_idx:] if next_heading_idx != -1 else ""
        content = f"{prefix}\n\n{lesson_block}\n{suffix}".rstrip() + "\n"
    else:
        content = content.rstrip() + f"\n\n---\n\n{lesson_block}\n"

    try:
        target_path.write_text(content, encoding="utf-8")
        return target_path
    except Exception:
        return None

