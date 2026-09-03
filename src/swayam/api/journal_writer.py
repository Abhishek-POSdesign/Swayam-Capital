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


def get_journal_dir(vault_path: Optional[Path] = None) -> Path:
    """Returns the path to the 04 - Journal directory in the vault, ensuring it exists."""
    base = vault_path or settings.vault_path
    journal_dir = base / "02 - Projects" / "Trading" / "04 - Journal"
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
) -> str:
    """Writes a new trade journal markdown note to Obsidian Second Brain.

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
    journal_dir = get_journal_dir(vault_path)
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
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

    max_loss_inr = float(payoff.get("max_loss_inr", 0.0))
    max_profit_inr = float(payoff.get("max_profit_inr", 0.0))
    rr_implied = float(payoff.get("rr_implied", 0.0))
    net_debit_credit = float(payoff.get("net_debit_credit_inr", 0.0))
    breakevens = payoff.get("breakevens", [])
    expiry_date = legs[0].get("expiry_date", date_str) if legs else date_str

    max_loss_pct = (max_loss_inr / margin_base_inr * 100.0) if margin_base_inr > 0 else 0.0

    # Build legs table rows
    leg_rows = []
    for idx, leg in enumerate(legs, start=1):
        leg_rows.append(
            f"| {idx} | {leg.get('strike'):,.0f} | {leg.get('option_type')} | "
            f"{leg.get('direction', '').upper()} | {leg.get('quantity_lots', 1)} | "
            f"₹{float(leg.get('entry_premium', 0.0)):,.2f} |"
        )
    legs_table = "\n".join(leg_rows)

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

    content = f"""---
trade_id: {position_id}
date: {date_str}
strategy: {strategy_name}
underlying: {underlying}
status: open
mode: paper
---

# {date_str} — Trade #{seq_str} — {strategy_name}

## Entry (paper trade)

- **Time opened**: {now.isoformat()}
- **NIFTY spot at entry**: {current_spot:,.2f}
- **Underlying**: {underlying}
- **Expiry**: {expiry_date}

### Legs

| # | Strike | Type | Direction | Lots | Entry Premium |
|:---:|---:|:---:|:---:|:---:|---:|
{legs_table}

### Risk / Reward

- **Max loss**: ₹{max_loss_inr:,.0f} ({max_loss_pct:.2f}% of margin base)
- **Max profit**: ₹{max_profit_inr:,.0f}
- **R:R implied**: {rr_implied:.2f}
- **Net debit/credit**: ₹{net_debit_credit:,.0f}
- **Breakeven(s)**: {breakeven_str}

### Greeks at entry

- Net Delta: {float(greeks.get('net_delta', 0.0)):.4f}
- Net Theta: ₹{float(greeks.get('net_theta_per_day', 0.0)):.0f}/day
- Net Vega: ₹{float(greeks.get('net_vega', 0.0)):.0f} per 1% IV
- Net Gamma: {float(greeks.get('net_gamma', 0.0)):.6f}

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

    rel_path = f"02 - Projects/Trading/04 - Journal/{filename}"
    return rel_path
