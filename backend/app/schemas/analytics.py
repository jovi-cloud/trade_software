"""Analytics response DTOs.

Every metric is exposed twice, deliberately and cheaply:

* as **typed groups** (``returns``, ``risk``, ...) so a consumer that knows the
  field it wants reads it directly and the generated TypeScript types carry it;
* as a flat **``metrics``** list where each entry carries its label, format,
  category and description, so a consumer that does *not* know the field names -
  a metric grid, a comparison table, a PDF section - iterates it without 60
  hard-coded labels.

Both views read the same computed values; nothing is calculated twice.

``float | None`` is used throughout and means *undefined for this run*, not zero:
a Sharpe ratio needs volatility, a profit factor needs a losing trade, and
reporting 0.0 instead would rank a flawless run below a mediocre one.
"""

from __future__ import annotations

from dataclasses import asdict

from pydantic import BaseModel, Field

from app.analytics.catalog import MetricCategory, MetricFormat
from app.analytics.report import AnalyticsReport


class MetricValueRead(BaseModel):
    """One metric with everything needed to display or compare it."""

    key: str
    label: str
    value: float | None
    format: MetricFormat
    precision: int
    category: MetricCategory
    description: str
    higher_is_better: bool | None
    is_headline: bool


class ReturnMetricsRead(BaseModel):
    net_profit: float
    gross_profit: float
    gross_loss: float
    total_return_pct: float
    annualised_return_pct: float | None
    cagr_pct: float | None
    average_trade: float
    average_win: float
    average_loss: float
    profit_factor: float | None
    expectancy: float
    recovery_factor: float | None
    payoff_ratio: float | None
    commission_paid: float
    slippage_cost: float
    final_equity: float


class RiskMetricsRead(BaseModel):
    max_drawdown: float
    max_drawdown_pct: float
    average_drawdown: float
    average_drawdown_pct: float
    longest_drawdown_ms: int
    longest_drawdown_bars: int
    drawdown_episodes: int
    ulcer_index: float | None
    volatility_pct: float | None
    annualised_volatility_pct: float | None
    downside_deviation_pct: float | None
    value_at_risk_pct: float | None
    conditional_value_at_risk_pct: float | None
    exposure_pct: float
    time_in_market_pct: float


class RiskAdjustedMetricsRead(BaseModel):
    sharpe_ratio: float | None
    sortino_ratio: float | None
    calmar_ratio: float | None
    mar_ratio: float | None
    information_ratio: float | None
    treynor_ratio: float | None


class TradeMetricsRead(BaseModel):
    total_trades: int = Field(ge=0)
    winning_trades: int = Field(ge=0)
    losing_trades: int = Field(ge=0)
    breakeven_trades: int = Field(ge=0)
    win_rate_pct: float
    loss_rate_pct: float
    longest_win_streak: int = Field(ge=0)
    longest_loss_streak: int = Field(ge=0)
    average_holding_time_ms: float
    max_holding_time_ms: int
    min_holding_time_ms: int
    average_bars_held: float
    average_mae: float | None
    average_mfe: float | None
    largest_winner: float
    largest_loser: float


class PortfolioMetricsRead(BaseModel):
    capital_utilisation_pct: float
    peak_capital_utilisation_pct: float
    cash_utilisation_pct: float


class StatisticalMetricsRead(BaseModel):
    sqn: float | None
    kelly_pct: float | None
    z_score: float | None
    edge_ratio: float | None


class EquityCurvePointRead(BaseModel):
    ts: int
    equity: float
    realised: float


class DrawdownPointRead(BaseModel):
    ts: int
    depth: float
    depth_pct: float


class DailyPnlPointRead(BaseModel):
    day_ms: int
    pnl: float
    return_pct: float
    equity: float


class RollingReturnPointRead(BaseModel):
    day_ms: int
    return_pct: float


class MonthlyReturnRead(BaseModel):
    year: int
    month: int = Field(ge=1, le=12)
    return_pct: float
    pnl: float
    start_equity: float
    end_equity: float
    trading_days: int = Field(ge=0)


class YearlyReturnRead(BaseModel):
    year: int
    return_pct: float
    pnl: float
    start_equity: float
    end_equity: float
    trading_days: int = Field(ge=0)


class PortfolioSeriesRead(BaseModel):
    """Curves and calendar tables.

    Per-bar curves are capped in length for transport; every scalar metric is
    still computed from the full series, and the extremes (equity peak, equity
    trough, deepest drawdown) are always among the emitted points, so a chart can
    never contradict a headline number. ``curves_downsampled`` says whether any
    thinning happened.
    """

    equity_curve: list[EquityCurvePointRead]
    drawdown_curve: list[DrawdownPointRead]
    daily_pnl: list[DailyPnlPointRead]
    rolling_returns: list[RollingReturnPointRead]
    monthly_returns: list[MonthlyReturnRead]
    yearly_returns: list[YearlyReturnRead]
    max_drawdown_start_ts: int | None
    max_drawdown_trough_ts: int | None
    max_drawdown_recovery_ts: int | None
    curves_downsampled: bool


class AnalyticsMetaRead(BaseModel):
    """The assumptions a report was computed under."""

    initial_capital: float
    bar_count: int = Field(ge=0)
    trade_count: int = Field(ge=0)
    trading_days: int = Field(ge=0)
    start_ts: int | None
    end_ts: int | None
    elapsed_ms: int = Field(ge=0)
    trading_days_per_year: int
    risk_free_rate_pct: float
    var_confidence_pct: float
    rolling_window_days: int
    analytics_version: str


class AnalyticsReportRead(BaseModel):
    """A complete performance and risk report for one run."""

    returns: ReturnMetricsRead
    risk: RiskMetricsRead
    risk_adjusted: RiskAdjustedMetricsRead
    trades: TradeMetricsRead
    portfolio: PortfolioMetricsRead
    statistics: StatisticalMetricsRead
    series: PortfolioSeriesRead
    meta: AnalyticsMetaRead
    metrics: list[MetricValueRead]


def analytics_report_read(report: AnalyticsReport) -> AnalyticsReportRead:
    """Convert an engine-side report into its API representation."""
    payload = asdict(report)
    payload["metrics"] = [asdict(value) for value in report.metric_values()]
    return AnalyticsReportRead.model_validate(payload)


def analytics_report_from_json(payload: str) -> AnalyticsReportRead:
    """Rehydrate a persisted report. Raises if the stored shape no longer validates."""
    return AnalyticsReportRead.model_validate_json(payload)
