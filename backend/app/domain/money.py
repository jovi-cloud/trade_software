"""Money rounding at fill and reporting boundaries (ARCHITECTURE.md 9)."""

from __future__ import annotations


def round_money(value: float, digits: int = 6) -> float:
    """Round a monetary value to avoid float noise in cash and P&L."""
    return round(value, digits)
