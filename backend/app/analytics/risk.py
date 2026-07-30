"""Risk metrics: dispersion, tail loss, drawdown and market exposure.

Every dispersion statistic is computed on **daily** returns and annualised with
``sqrt(252)``. Sampling to days before annualising is what makes a 1m run and a
1d run of the same idea directly comparable; annualising raw bar returns would
scale one of them by ~20x more than the other for no economic reason.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.analytics import _numeric as num
from app.analytics.drawdown import DrawdownMetrics
from app.analytics.equity import DailySeries, EquitySeries, FloatArray
from app.analytics.inputs import TRADING_DAYS_PER_YEAR, AnalyticsConfig, TradeRecord

ANNUALISATION = float(np.sqrt(TRADING_DAYS_PER_YEAR))


@dataclass(frozen=True)
class RiskMetrics:
    """How much pain the run inflicted, and how much of the time it was exposed."""

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


@dataclass(frozen=True)
class DispersionBasis:
    """Daily dispersion terms the risk-adjusted ratios reuse.

    Computed once and passed along so Sharpe and Sortino never recompute the
    standard deviation the volatility metrics already produced.
    """

    excess_returns_pct: FloatArray
    daily_stdev_pct: float | None
    daily_downside_deviation_pct: float | None


def build_dispersion_basis(daily: DailySeries, config: AnalyticsConfig) -> DispersionBasis:
    """Daily excess returns and their dispersion, relative to the risk-free hurdle."""
    if daily.is_empty:
        empty = np.zeros(0, dtype=np.float64)
        return DispersionBasis(
            excess_returns_pct=empty,
            daily_stdev_pct=None,
            daily_downside_deviation_pct=None,
        )

    excess = daily.returns_pct - config.daily_risk_free_pct
    return DispersionBasis(
        excess_returns_pct=excess,
        daily_stdev_pct=num.sample_stdev(daily.returns_pct),
        daily_downside_deviation_pct=_downside_deviation(excess),
    )


def _downside_deviation(excess_returns_pct: FloatArray) -> float | None:
    """Root mean square of shortfalls below the hurdle.

    Full-sample denominator (every day, not just losing days), which is the
    standard Sortino definition: a strategy with few but severe shortfalls
    should not be rewarded for the days it stayed above water.
    """
    if excess_returns_pct.size == 0:
        return None
    shortfall = np.minimum(excess_returns_pct, 0.0)
    deviation = float(np.sqrt(np.mean(np.square(shortfall))))
    return deviation if deviation > 0.0 else None


def compute_risk_metrics(
    *,
    series: EquitySeries,
    daily: DailySeries,
    dispersion: DispersionBasis,
    drawdown: DrawdownMetrics,
    trades: tuple[TradeRecord, ...],
    config: AnalyticsConfig,
) -> RiskMetrics:
    """Assemble the risk group from series already built upstream."""
    return RiskMetrics(
        max_drawdown=drawdown.max_drawdown,
        max_drawdown_pct=drawdown.max_drawdown_pct,
        average_drawdown=drawdown.average_drawdown,
        average_drawdown_pct=drawdown.average_drawdown_pct,
        longest_drawdown_ms=drawdown.longest_drawdown_ms,
        longest_drawdown_bars=drawdown.longest_drawdown_bars,
        drawdown_episodes=drawdown.drawdown_episodes,
        ulcer_index=drawdown.ulcer_index,
        volatility_pct=num.ratio(dispersion.daily_stdev_pct),
        annualised_volatility_pct=(
            None
            if dispersion.daily_stdev_pct is None
            else num.percent(dispersion.daily_stdev_pct * ANNUALISATION)
        ),
        downside_deviation_pct=(
            None
            if dispersion.daily_downside_deviation_pct is None
            else num.percent(dispersion.daily_downside_deviation_pct * ANNUALISATION)
        ),
        value_at_risk_pct=_value_at_risk(daily, config),
        conditional_value_at_risk_pct=_conditional_value_at_risk(daily, config),
        exposure_pct=_exposure_pct(series),
        time_in_market_pct=_time_in_market_pct(series, trades),
    )


def _value_at_risk(daily: DailySeries, config: AnalyticsConfig) -> float | None:
    """Historical Value at Risk on daily returns.

    The empirical percentile - no distributional assumption. Reported as a loss
    magnitude: 1.8 means "on the worst 5% of days, the account lost at least
    1.8%". A negative value means the run made money even at that percentile.
    """
    if daily.day_count < 2:
        return None
    tail = 100.0 - config.var_confidence_pct
    return num.percent(-float(np.percentile(daily.returns_pct, tail)))


def _conditional_value_at_risk(daily: DailySeries, config: AnalyticsConfig) -> float | None:
    """Expected loss on the days that breach VaR (expected shortfall).

    Averages the tail rather than reading its edge, so a fat tail shows up here
    even when VaR looks tame.
    """
    if daily.day_count < 2:
        return None
    tail = 100.0 - config.var_confidence_pct
    threshold = float(np.percentile(daily.returns_pct, tail))
    breaches = daily.returns_pct[daily.returns_pct <= threshold]
    if breaches.size == 0:
        return None
    return num.percent(-float(np.mean(breaches)))


def _exposure_pct(series: EquitySeries) -> float:
    """Share of bars with a position open at the close.

    Bar-weighted. Together with time in market this separates "how many
    opportunities did the strategy take" from "how long was capital at risk in
    wall-clock terms" - the two diverge sharply on intraday data, where a
    position held across a session gap occupies few bars but many hours.
    """
    if series.is_empty:
        return 0.0
    return num.percent(series.bars_in_position / series.bar_count * 100.0)


def _time_in_market_pct(series: EquitySeries, trades: tuple[TradeRecord, ...]) -> float:
    """Share of elapsed calendar time spent holding a position."""
    elapsed = series.elapsed_ms
    if elapsed <= 0 or not trades:
        return 0.0
    held = sum(max(trade.exit_ts - trade.entry_ts, 0) for trade in trades)
    return num.percent(min(held / elapsed * 100.0, 100.0))
