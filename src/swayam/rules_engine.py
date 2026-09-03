"""
Rules Engine & Tolerant Comparison Module for Swayam Capital.

This module provides the `TolerantComparator` class which applies a configurable
percentage tolerance band (default 2%) to all rule evaluations (ceilings and floors).
No component in Swayam Capital evaluates raw strict comparisons directly against
rule thresholds; all risk checks flow through this module.
"""

from typing import Optional


class TolerantComparator:
    """Applies a tolerance band to numerical rule evaluations (caps and floors).

    Attributes:
        tolerance_pct (float): Fractional tolerance buffer (e.g. 0.02 for 2%).
    """

    def __init__(self, tolerance_pct: float = 0.02) -> None:
        """Initializes the comparator with a given percentage tolerance.

        Args:
            tolerance_pct: Percentage buffer as a fraction (e.g., 0.02 = 2%).
        """
        if tolerance_pct < 0.0:
            raise ValueError("tolerance_pct cannot be negative.")
        self.tolerance_pct: float = tolerance_pct

    def within_cap(self, actual: float, cap: float) -> bool:
        """Evaluates whether an actual value respects an upper ceiling/cap.

        Returns True if `actual <= cap * (1 + tolerance_pct)`.
        For example, with a ₹10,000 cap and 2% tolerance, actual values up to
        ₹10,200 will pass.

        Args:
            actual: The measured or requested quantity (e.g., trade risk in ₹).
            cap: The nominal maximum ceiling.

        Returns:
            bool: True if within the tolerant cap, False otherwise.
        """
        effective_cap = cap * (1.0 + self.tolerance_pct)
        return actual <= effective_cap

    def meets_floor(self, actual: float, floor: float) -> bool:
        """Evaluates whether an actual value meets a lower target/floor.

        Returns True if `actual >= floor * (1 - tolerance_pct)`.
        For example, with a 2.0 R:R minimum floor and 2% tolerance, actual values
        down to 1.96 will pass.

        Args:
            actual: The measured or planned quantity (e.g., R:R ratio).
            floor: The nominal minimum floor.

        Returns:
            bool: True if meeting or exceeding the tolerant floor, False otherwise.
        """
        effective_floor = floor * (1.0 - self.tolerance_pct)
        return actual >= effective_floor

    def evaluate_cap(self, actual: float, cap: float) -> tuple[bool, float, float]:
        """Returns verdict and comparison figures for an upper ceiling check.

        Args:
            actual: The measured quantity.
            cap: The nominal ceiling.

        Returns:
            tuple[bool, float, float]: (passed, actual, effective_cap)
        """
        effective_cap = cap * (1.0 + self.tolerance_pct)
        return (actual <= effective_cap, actual, effective_cap)

    def evaluate_floor(self, actual: float, floor: float) -> tuple[bool, float, float]:
        """Returns verdict and comparison figures for a lower floor check.

        Args:
            actual: The measured quantity.
            floor: The nominal floor.

        Returns:
            tuple[bool, float, float]: (passed, actual, effective_floor)
        """
        effective_floor = floor * (1.0 - self.tolerance_pct)
        return (actual >= effective_floor, actual, effective_floor)


def compute_rupee_cap(pct: float, margin_base_inr: float) -> float:
    """Computes dynamic rupee limit from percentage and current margin base.

    Args:
        pct: Risk percentage (e.g. 0.01 for 1%).
        margin_base_inr: Current total margin base in INR (e.g. 850000.0).

    Returns:
        float: Rupee ceiling.
    """
    return pct * margin_base_inr
