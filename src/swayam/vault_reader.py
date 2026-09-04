"""
Obsidian Second Brain Method Files Reader for Swayam Capital.

This module parses Abhishek Sikka's Method markdown files from the Obsidian vault
at runtime, extracting trading, risk, and operational readiness rules as percentages
(never hardcoded rupee amounts). It exposes a typed `MethodRules` dataclass and
provides dynamic calculation of rupee limits based on the current margin base.
"""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Optional


class MethodRulesParseError(Exception):
    """Raised when a mandatory rule cannot be found or parsed from a Method file."""
    pass


@dataclass(frozen=True)
class MethodRules:
    """Typed data structure representing parsed Method rules from the Obsidian vault."""

    # Risk Management Rules (Stored strictly as fractions/percentages)
    per_trade_risk_pct: float       # 0.01 for 1%
    realistic_risk_cap_pct: float   # 0.01 for 1%
    realistic_stress_sigma: float   # 2.0
    realized_vol_window_days: int   # 20
    rr_minimum: float               # 2.0 for 1:2
    rr_target: float                # 2.5 for 1:2.5
    daily_loss_cap_pct: float       # 0.02 for 2%
    weekly_loss_cap_pct: float      # 0.04 for 4%
    blast_radius_pct: float         # 0.03 for 3%
    overnight_hedge_cap_pct: float  # 0.02 for 2%

    # Margin Base Context
    margin_base_min_inr: float      # e.g., 800000.0
    margin_base_max_inr: float      # e.g., 900000.0
    margin_base_default_inr: float  # e.g., 850000.0

    # Operational Readiness Rules
    sleep_no_trade_threshold_hours: float  # 5.0
    sleep_reduced_size_hours_min: float    # 5.0
    sleep_reduced_size_hours_max: float    # 6.0
    sleep_reduced_size_factor: float       # 0.75 (75% sizing)
    alcohol_lockout_days: int              # 90 days

    # Re-entry Ramp Tiers: tuple of ((min_day, max_day), risk_cap_pct)
    # Parsed dynamically from Operational Readiness Rules § Factor 2 (no hardcoded default)
    reentry_ramp: tuple[tuple[tuple[int, Optional[int]], float], ...]

    def calculate_per_trade_rupee_cap(self, margin_base: Optional[float] = None) -> float:
        """Calculates effective per-trade rupee cap from percentage × margin base."""
        base = margin_base if margin_base is not None else self.margin_base_default_inr
        return self.per_trade_risk_pct * base

    def calculate_realistic_risk_rupee_cap(self, margin_base: Optional[float] = None) -> float:
        """Calculates effective realistic risk rupee cap from percentage × margin base."""
        base = margin_base if margin_base is not None else self.margin_base_default_inr
        return self.realistic_risk_cap_pct * base

    def calculate_daily_loss_rupee_cap(self, margin_base: Optional[float] = None) -> float:
        """Calculates effective daily loss rupee cap from percentage × margin base."""
        base = margin_base if margin_base is not None else self.margin_base_default_inr
        return self.daily_loss_cap_pct * base

    def calculate_weekly_loss_rupee_cap(self, margin_base: Optional[float] = None) -> float:
        """Calculates effective weekly loss rupee cap from percentage × margin base."""
        base = margin_base if margin_base is not None else self.margin_base_default_inr
        return self.weekly_loss_cap_pct * base

    def calculate_blast_radius_rupee_cap(self, margin_base: Optional[float] = None) -> float:
        """Calculates single-trade system failure rupee fuse from percentage × margin base."""
        base = margin_base if margin_base is not None else self.margin_base_default_inr
        return self.blast_radius_pct * base

    def calculate_overnight_hedge_rupee_cap(self, margin_base: Optional[float] = None) -> float:
        """Calculates maximum next-day gap loss rupee limit from percentage × margin base."""
        base = margin_base if margin_base is not None else self.margin_base_default_inr
        return self.overnight_hedge_cap_pct * base


class VaultReader:
    """Reads and monitors Method markdown files from the Second Brain."""

    def __init__(
        self,
        method_dir: Optional[Path] = None,
        brief_file: Optional[Path] = None,
        operational_file: Optional[Path] = None,
    ) -> None:
        from swayam.config import settings
        self.method_dir = Path(method_dir) if method_dir else settings.trading_method_path
        self.brief_file = Path(brief_file) if brief_file else settings.trading_brief_path
        self.risk_file = self.method_dir / "Risk Management Rules.md"
        self.operational_file = (
            Path(operational_file)
            if operational_file
            else self.method_dir / "Operational Readiness Rules.md"
        )
        self._cached_rules: Optional[MethodRules] = None
        self._cached_mtimes: dict[Path, float] = {}

    def _get_mtimes(self) -> dict[Path, float]:
        """Returns the current modification times of the watched rule files."""
        mtimes = {}
        for p in [self.risk_file, self.brief_file, self.operational_file]:
            if p.exists():
                mtimes[p] = p.stat().st_mtime
        return mtimes

    def should_reload(self) -> bool:
        """Checks if any watched Method file has been modified since last load."""
        if self._cached_rules is None:
            return True
        current_mtimes = self._get_mtimes()
        return current_mtimes != self._cached_mtimes

    def load_rules(self, force_reload: bool = False) -> MethodRules:
        """Loads and parses Method rules, using memory cache unless files changed."""
        if not force_reload and self._cached_rules is not None and not self.should_reload():
            return self._cached_rules

        # Ensure files exist
        for f, desc in [
            (self.risk_file, "Risk Management Rules"),
            (self.operational_file, "Operational Readiness Rules"),
            (self.brief_file, "Personal Trading Brief"),
        ]:
            if not f.exists():
                raise MethodRulesParseError(f"Missing mandatory Method file ({desc}): {f}")

        risk_text = self.risk_file.read_text(encoding="utf-8")
        op_text = self.operational_file.read_text(encoding="utf-8")
        brief_text = self.brief_file.read_text(encoding="utf-8")

        parsed = self._parse_all_rules(risk_text, op_text, brief_text)
        self._cached_rules = parsed
        self._cached_mtimes = self._get_mtimes()
        return parsed

    def _parse_reentry_ramp(self, op_text: str) -> tuple[tuple[tuple[int, Optional[int]], float], ...]:
        """Parses the 4-tier re-entry ramp from Operational Readiness Rules § Factor 2."""
        tier_pattern = (
            r"\*\*Days?\s+(\d+)(?:[-–](\d+))?\+?[^*]*\*\*[:\s]*.*?"
            r"(\d+(?:\.\d+)?)%\s+(?:risk\s+per\s+trade\s+cap|cap\s+resumes)"
        )
        matches = list(re.finditer(tier_pattern, op_text, re.IGNORECASE))
        if len(matches) < 4:
            raise MethodRulesParseError(
                f"Could not parse at least 4 tiers for reentry_ramp from Operational Readiness Rules. Found {len(matches)}."
            )
        tiers = []
        for m in matches:
            start_day = int(m.group(1))
            end_day = int(m.group(2)) if m.group(2) else None
            risk_pct = float(m.group(3)) / 100.0
            tiers.append(((start_day, end_day), risk_pct))
        return tuple(tiers)

    def _parse_all_rules(self, risk_text: str, op_text: str, brief_text: str) -> MethodRules:
        """Internal parsing logic with strict regex extraction."""

        # 1. Per-trade risk cap (e.g., "1% of margin base per trade")
        m = re.search(r"(\d+(?:\.\d+)?)%\s+of\s+margin\s+base\s+per\s+trade", risk_text, re.IGNORECASE)
        if not m:
            raise MethodRulesParseError("Could not parse per_trade_risk_pct in Risk Management Rules")
        per_trade_risk_pct = float(m.group(1)) / 100.0

        # 2. R:R Minimum (e.g., "Phase 1 minimum: 1:2 R:R")
        m = re.search(r"minimum:\s*1:(\d+(?:\.\d+)?)\s*R:R", risk_text, re.IGNORECASE)
        if not m:
            raise MethodRulesParseError("Could not parse rr_minimum in Risk Management Rules")
        rr_minimum = float(m.group(1))

        # 3. R:R Target (e.g., "Phase 1 target: 1:2.5 R:R")
        m = re.search(r"target:\s*1:(\d+(?:\.\d+)?)\s*R:R", risk_text, re.IGNORECASE)
        if not m:
            raise MethodRulesParseError("Could not parse rr_target in Risk Management Rules")
        rr_target = float(m.group(1))

        # 4. Daily Loss Cap (e.g., "Daily loss cap: 2% of margin base")
        m = re.search(r"Daily\s+loss\s+cap:\s*(\d+(?:\.\d+)?)%\s+of\s+margin\s+base", risk_text, re.IGNORECASE)
        if not m:
            raise MethodRulesParseError("Could not parse daily_loss_cap_pct in Risk Management Rules")
        daily_loss_cap_pct = float(m.group(1)) / 100.0

        # 5. Weekly Loss Cap (e.g., "Weekly loss cap: 4% of margin base")
        m = re.search(r"Weekly\s+loss\s+cap:\s*(\d+(?:\.\d+)?)%\s+of\s+margin\s+base", risk_text, re.IGNORECASE)
        if not m:
            raise MethodRulesParseError("Could not parse weekly_loss_cap_pct in Risk Management Rules")
        weekly_loss_cap_pct = float(m.group(1)) / 100.0

        # 6. Blast Radius (e.g., "realized loss exceeds 3% of margin base")
        m = re.search(r"exceeds\s*(\d+(?:\.\d+)?)%\s+of\s+margin\s+base", risk_text, re.IGNORECASE)
        if not m:
            raise MethodRulesParseError("Could not parse blast_radius_pct in Risk Management Rules")
        blast_radius_pct = float(m.group(1)) / 100.0

        # 7. Overnight Hedge Cap (e.g., "cannot lose more than 2% of margin base")
        m = re.search(r"cannot\s+lose\s+more\s+than\s*(\d+(?:\.\d+)?)%\s+of\s+margin\s+base", risk_text, re.IGNORECASE)
        if not m:
            raise MethodRulesParseError("Could not parse overnight_hedge_cap_pct in Risk Management Rules")
        overnight_hedge_cap_pct = float(m.group(1)) / 100.0

        # 8. Margin Base Range from Personal Trading Brief or Risk Management Rules (~₹8–9 lakh)
        combined_text = brief_text + "\n" + risk_text
        m = re.search(r"₹\s*(\d+)\s*[-–]\s*(\d+)\s*lakh", combined_text, re.IGNORECASE)
        if not m:
            raise MethodRulesParseError(
                "Could not parse margin_base range ('₹X–Y lakh') from Personal Trading Brief. "
                "The vault may have drifted or the range format changed."
            )
        margin_min = float(m.group(1)) * 100000.0
        margin_max = float(m.group(2)) * 100000.0
        margin_default = (margin_min + margin_max) / 2.0

        # 9. Sleep thresholds from Operational Readiness Rules
        # No trade: < 5 hours
        m = re.search(r"<\s*(\d+(?:\.\d+)?)\s*hours.*?No\s+trading", op_text, re.IGNORECASE | re.DOTALL)
        if not m:
            raise MethodRulesParseError(
                "Could not parse sleep_no_trade_threshold_hours from Operational Readiness Rules § Sleep."
            )
        sleep_no_trade = float(m.group(1))

        # Reduced size: 5–6 hours -> 75%
        m = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*hours.*?(\d+)%\s+of\s+normal", op_text, re.IGNORECASE | re.DOTALL)
        if not m:
            raise MethodRulesParseError(
                "Could not parse sleep_reduced_size params (e.g. '5–6 hours ... 75% of normal') "
                "from Operational Readiness Rules § Sleep."
            )
        sleep_red_min = float(m.group(1))
        sleep_red_max = float(m.group(2))
        sleep_red_factor = float(m.group(3)) / 100.0

        # 10. Alcohol lockout days (90 days / 3 months)
        m = re.search(r"(\d+)[-\s]day\s+(?:lockout|clock)", op_text, re.IGNORECASE)
        if not m:
            raise MethodRulesParseError(
                "Could not parse alcohol_lockout_days from Operational Readiness Rules Factor 2. "
                "Expected a phrase like 'X-day lockout' or 'X-day clock'."
            )
        alcohol_lockout = int(m.group(1))

        # 11. Re-entry ramp tiers
        reentry_ramp = self._parse_reentry_ramp(op_text)

        # 12. Two-tier risk model parameters (realistic risk cap, stress sigma, window days)
        m = re.search(r"realistic_risk_cap_pct:\s*`?([^\s`—\n\r]+)", risk_text, re.IGNORECASE)
        if not m:
            raise MethodRulesParseError("Could not parse realistic_risk_cap_pct in Risk Management Rules")
        try:
            realistic_risk_cap_pct = float(m.group(1).rstrip("%")) / 100.0
        except ValueError:
            raise MethodRulesParseError(f"Malformed realistic_risk_cap_pct in Risk Management Rules: {m.group(1)}")

        m = re.search(r"realistic_stress_sigma:\s*`?([^\s`—\n\r]+)", risk_text, re.IGNORECASE)
        if not m:
            raise MethodRulesParseError("Could not parse realistic_stress_sigma in Risk Management Rules")
        try:
            realistic_stress_sigma = float(m.group(1))
        except ValueError:
            raise MethodRulesParseError(f"Malformed realistic_stress_sigma in Risk Management Rules: {m.group(1)}")

        m = re.search(r"realized_vol_window_days:\s*`?([^\s`—\n\r]+)", risk_text, re.IGNORECASE)
        if not m:
            raise MethodRulesParseError("Could not parse realized_vol_window_days in Risk Management Rules")
        try:
            realized_vol_window_days = int(m.group(1))
        except ValueError:
            raise MethodRulesParseError(f"Malformed realized_vol_window_days in Risk Management Rules: {m.group(1)}")

        return MethodRules(
            per_trade_risk_pct=per_trade_risk_pct,
            realistic_risk_cap_pct=realistic_risk_cap_pct,
            realistic_stress_sigma=realistic_stress_sigma,
            realized_vol_window_days=realized_vol_window_days,
            rr_minimum=rr_minimum,
            rr_target=rr_target,
            daily_loss_cap_pct=daily_loss_cap_pct,
            weekly_loss_cap_pct=weekly_loss_cap_pct,
            blast_radius_pct=blast_radius_pct,
            overnight_hedge_cap_pct=overnight_hedge_cap_pct,
            margin_base_min_inr=margin_min,
            margin_base_max_inr=margin_max,
            margin_base_default_inr=margin_default,
            sleep_no_trade_threshold_hours=sleep_no_trade,
            sleep_reduced_size_hours_min=sleep_red_min,
            sleep_reduced_size_hours_max=sleep_red_max,
            sleep_reduced_size_factor=sleep_red_factor,
            alcohol_lockout_days=alcohol_lockout,
            reentry_ramp=reentry_ramp,
        )


vault_reader = VaultReader()
