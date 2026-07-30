"""Data-layer exceptions.

Raised only for structural problems that make a CSV unusable at all. Row-level
data-quality issues (bad timestamps, bad prices, duplicates, gaps) are never
raised - they are counted and returned in a ``ValidationReport`` so the import
report shows exactly what happened instead of silently dropping bad data.
"""

from __future__ import annotations


class MissingColumnsError(Exception):
    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__(f"CSV is missing required columns: {', '.join(missing)}")


class InvalidBarsError(Exception):
    """Raised when stored bars fail strict validation before a backtest run."""

    def __init__(self, message: str, *, summary: object | None = None) -> None:
        self.summary = summary
        super().__init__(message)
