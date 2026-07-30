"""Run comparison: side-by-side analysis of persisted AnalyticsReports.

Consumes existing analytics output only — no metrics are recalculated. The
comparison layer sits beside analytics the same way analytics sits beside the
engine:

    Run A/B/C → AnalyticsReport (already persisted)
                        ↓
              RunComparison.compare()
                        ↓
              ComparisonReport → API → UI
"""

from __future__ import annotations

from app.comparison._constants import COMPARISON_VERSION, MAX_RUNS, MIN_RUNS
from app.comparison.engine import RunComparison, compare
from app.comparison.inputs import ComparedRunInput
from app.comparison.report import ComparisonReport

__all__ = [
    "COMPARISON_VERSION",
    "MAX_RUNS",
    "MIN_RUNS",
    "ComparedRunInput",
    "ComparisonReport",
    "RunComparison",
    "compare",
]
