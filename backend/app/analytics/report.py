"""The report object: grouped metrics, curves, and the assumptions behind them.

``AnalyticsReport`` is the single thing every consumer receives - the API, Run
Comparison, Optimisation, Walk Forward, Monte Carlo, and PDF export. Groups are
typed dataclasses so a consumer can read ``report.risk.sharpe_ratio`` directly;
``metric_values()`` flattens the same numbers against the catalog so a consumer
that does *not* know the field names (a comparison table, a report template) can
iterate them with labels, formats and descriptions attached.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.analytics.catalog import METRIC_DEFINITIONS, MetricCategory, MetricFormat
from app.analytics.inputs import TRADING_DAYS_PER_YEAR, AnalyticsConfig
from app.analytics.portfolio import PortfolioMetrics, PortfolioSeries
from app.analytics.returns import ReturnMetrics
from app.analytics.risk import RiskMetrics
from app.analytics.risk_adjusted import RiskAdjustedMetrics
from app.analytics.statistics import StatisticalMetrics
from app.analytics.trades import TradeMetrics


@dataclass(frozen=True, slots=True)
class MetricValue:
    """One metric, ready to display or compare without further lookup.

    ``value`` is ``None`` when the metric is undefined for this run (no trades,
    zero volatility, no drawdown to divide by) - never a stand-in zero.
    """

    key: str
    label: str
    value: float | None
    format: MetricFormat
    precision: int
    category: MetricCategory
    description: str
    higher_is_better: bool | None
    is_headline: bool


@dataclass(frozen=True)
class AnalyticsMeta:
    """The context a number was produced in.

    Persisted with the report so a saved metric can always be traced back to the
    assumptions that produced it - the difference between a reproducible result
    and a number in a spreadsheet.
    """

    initial_capital: float
    bar_count: int
    trade_count: int
    trading_days: int
    start_ts: int | None
    end_ts: int | None
    elapsed_ms: int
    trading_days_per_year: int
    risk_free_rate_pct: float
    var_confidence_pct: float
    rolling_window_days: int
    analytics_version: str


@dataclass(frozen=True)
class AnalyticsReport:
    """A complete quantitative research report for one run."""

    returns: ReturnMetrics
    risk: RiskMetrics
    risk_adjusted: RiskAdjustedMetrics
    trades: TradeMetrics
    portfolio: PortfolioMetrics
    statistics: StatisticalMetrics
    series: PortfolioSeries
    meta: AnalyticsMeta

    def group(self, category: MetricCategory) -> object:
        """The dataclass holding one category's scalars."""
        return getattr(self, category.value)

    def metric_values(self) -> tuple[MetricValue, ...]:
        """Every scalar metric, in catalog order, with its presentation metadata.

        Catalog order is the display and comparison order everywhere. Adding a
        metric means adding a definition and a field - no consumer changes.
        """
        return tuple(
            MetricValue(
                key=definition.key,
                label=definition.label,
                value=_as_optional_float(getattr(self.group(definition.category), definition.key)),
                format=definition.format,
                precision=definition.precision,
                category=definition.category,
                description=definition.description,
                higher_is_better=definition.higher_is_better,
                is_headline=definition.is_headline,
            )
            for definition in METRIC_DEFINITIONS
        )

    def metric(self, key: str) -> MetricValue | None:
        """One metric by key, for a comparison that asks for specific columns."""
        return next((value for value in self.metric_values() if value.key == key), None)


def _as_optional_float(value: object) -> float | None:
    """Normalise a group field to the ``float | None`` the API contract promises."""
    if value is None:
        return None
    if isinstance(value, bool):  # pragma: no cover - no boolean metrics today
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    raise TypeError(f"Metric value must be numeric, got {type(value).__name__}")


def meta_from(
    *,
    initial_capital: float,
    bar_count: int,
    trade_count: int,
    trading_days: int,
    start_ts: int | None,
    end_ts: int | None,
    elapsed_ms: int,
    config: AnalyticsConfig,
    analytics_version: str,
) -> AnalyticsMeta:
    """Build the meta block from the inputs a report was computed under."""
    return AnalyticsMeta(
        initial_capital=initial_capital,
        bar_count=bar_count,
        trade_count=trade_count,
        trading_days=trading_days,
        start_ts=start_ts,
        end_ts=end_ts,
        elapsed_ms=elapsed_ms,
        trading_days_per_year=TRADING_DAYS_PER_YEAR,
        risk_free_rate_pct=config.risk_free_rate_pct,
        var_confidence_pct=config.var_confidence_pct,
        rolling_window_days=config.rolling_window_days,
        analytics_version=analytics_version,
    )
