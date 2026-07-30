"""Performance and risk analytics.

A pure, framework-free leaf layer that sits *beside* the execution engine, not
inside it:

    ExecutionEngine -> ExecutionResult -> PerformanceAnalytics -> AnalyticsReport

The engine produces trades and bars. This layer turns them into a quantitative
research report. It imports nothing but ``app.domain`` and numpy, which is what
lets optimisation, walk-forward, Monte Carlo and PDF reporting all reuse it by
calling one function - no engine change, no database, no HTTP.

Every formula and annualisation assumption is documented in ``docs/metrics.md``.
"""

from __future__ import annotations

from app.analytics.catalog import METRIC_DEFINITIONS, MetricDefinition, MetricFormat
from app.analytics.inputs import AnalyticsConfig, AnalyticsInput, BarRecord, TradeRecord
from app.analytics.metrics import PerformanceAnalytics, analyse
from app.analytics.report import AnalyticsMeta, AnalyticsReport, MetricValue
from app.analytics.serialize import report_from_json

__all__ = [
    "METRIC_DEFINITIONS",
    "AnalyticsConfig",
    "AnalyticsInput",
    "AnalyticsMeta",
    "AnalyticsReport",
    "BarRecord",
    "MetricDefinition",
    "MetricFormat",
    "MetricValue",
    "PerformanceAnalytics",
    "TradeRecord",
    "analyse",
    "report_from_json",
]
