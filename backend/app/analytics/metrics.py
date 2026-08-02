"""The analytics entry point.

One call, one pass. The order below is the dependency order, and it is the whole
reason this layer has no duplicated arithmetic:

1. per-bar equity curve         (from bars + closed trades)
2. daily equity + daily returns (from the equity curve)
3. drawdown series              (from the equity curve)
4. dispersion terms             (from daily returns; reused by Sharpe/Sortino)
5. trade excursions             (from bars + trades)
6. the six metric groups, each reading only what is above it
7. the emitted curves and tables

Nothing recomputes a standard deviation, a running peak, or a daily return.
"""

from __future__ import annotations

from app.analytics.drawdown import build_drawdown_series, compute_drawdown_metrics
from app.analytics.equity import build_daily_series, build_equity_series
from app.analytics.inputs import AnalyticsInput
from app.analytics.monthly import compute_monthly_returns
from app.analytics.portfolio import build_portfolio_series, compute_portfolio_metrics
from app.analytics.report import AnalyticsReport, meta_from
from app.analytics.returns import compute_return_metrics
from app.analytics.risk import build_dispersion_basis, compute_risk_metrics
from app.analytics.risk_adjusted import compute_risk_adjusted_metrics
from app.analytics.statistics import compute_statistical_metrics
from app.analytics.trades import compute_excursions, compute_trade_metrics
from app.analytics.yearly import compute_yearly_returns

#: Bumped whenever a formula changes in a way that moves a reported number.
#: Recorded on every report and persisted with every run, so a number that looks
#: wrong six months from now can be attributed to the code that produced it -
#: the same reasoning as ``engine_version`` in ARCHITECTURE.md 10.
ANALYTICS_VERSION = "1.0.0"


class PerformanceAnalytics:
    """Turns one run's trades and bars into a complete research report.

    Deterministic and stateless: the same input always produces the same report,
    and an instance can be reused across runs.
    """

    def analyse(self, data: AnalyticsInput) -> AnalyticsReport:
        """Compute every metric, curve and table for one run."""
        config = data.config

        series = build_equity_series(
            bars=data.bars,
            trades=data.trades,
            initial_capital=data.initial_capital,
        )
        daily = build_daily_series(series, timezone=config.session_timezone)
        drawdowns = build_drawdown_series(series)
        drawdown_metrics = compute_drawdown_metrics(drawdowns)
        dispersion = build_dispersion_basis(daily, config)
        excursions = compute_excursions(trades=data.trades, series=series)

        returns = compute_return_metrics(
            trades=data.trades,
            initial_capital=data.initial_capital,
            final_equity=series.final_equity,
            max_drawdown=drawdown_metrics.max_drawdown,
            elapsed_ms=series.elapsed_ms,
        )
        risk = compute_risk_metrics(
            series=series,
            daily=daily,
            dispersion=dispersion,
            drawdown=drawdown_metrics,
            trades=data.trades,
            config=config,
        )
        risk_adjusted = compute_risk_adjusted_metrics(
            dispersion=dispersion,
            annualised_return_pct=returns.annualised_return_pct,
            cagr_pct=returns.cagr_pct,
            max_drawdown_pct=drawdown_metrics.max_drawdown_pct,
            config=config,
        )
        trade_metrics = compute_trade_metrics(trades=data.trades, excursions=excursions)
        portfolio = compute_portfolio_metrics(series)
        statistics = compute_statistical_metrics(
            trades=data.trades,
            trade_metrics=trade_metrics,
            returns=returns,
            excursions=excursions,
        )

        portfolio_series = build_portfolio_series(
            series=series,
            drawdowns=drawdowns,
            drawdown_metrics=drawdown_metrics,
            daily=daily,
            monthly_returns=compute_monthly_returns(
                daily, initial_capital=data.initial_capital, timezone=config.session_timezone
            ),
            yearly_returns=compute_yearly_returns(
                daily, initial_capital=data.initial_capital, timezone=config.session_timezone
            ),
            config=config,
        )

        return AnalyticsReport(
            returns=returns,
            risk=risk,
            risk_adjusted=risk_adjusted,
            trades=trade_metrics,
            portfolio=portfolio,
            statistics=statistics,
            series=portfolio_series,
            meta=meta_from(
                initial_capital=data.initial_capital,
                bar_count=series.bar_count,
                trade_count=len(data.trades),
                trading_days=daily.day_count,
                start_ts=series.start_ts,
                end_ts=series.end_ts,
                elapsed_ms=series.elapsed_ms,
                config=config,
                analytics_version=ANALYTICS_VERSION,
            ),
        )


def analyse(data: AnalyticsInput) -> AnalyticsReport:
    """Module-level shorthand for ``PerformanceAnalytics().analyse(data)``."""
    return PerformanceAnalytics().analyse(data)
