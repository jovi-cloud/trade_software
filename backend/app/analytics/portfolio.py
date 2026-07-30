"""Portfolio-level series and capital utilisation.

The curves emitted here are for display and export. Scalars everywhere else in
the report are always computed from the **full** series; only the emitted points
are thinned, and the thinning preserves the extremes so a peak or a trough can
never be sampled away. That bound is what lets a run on a year of 1m bars return
a report over HTTP without a second request.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.analytics import _numeric as num
from app.analytics.drawdown import DrawdownMetrics, DrawdownSeries
from app.analytics.equity import DailySeries, EquitySeries
from app.analytics.inputs import AnalyticsConfig
from app.analytics.monthly import MonthlyReturn
from app.analytics.yearly import YearlyReturn


@dataclass(frozen=True, slots=True)
class EquityPoint:
    """Mark-to-market account equity at one bar close."""

    ts: int
    equity: float
    realised: float


@dataclass(frozen=True, slots=True)
class DrawdownPoint:
    """Distance below the running equity peak at one bar close."""

    ts: int
    depth: float
    depth_pct: float


@dataclass(frozen=True, slots=True)
class DailyPnlPoint:
    """One UTC trading day's change in equity."""

    day_ms: int
    pnl: float
    return_pct: float
    equity: float


@dataclass(frozen=True, slots=True)
class RollingReturnPoint:
    """Trailing-window return ending on this day."""

    day_ms: int
    return_pct: float


@dataclass(frozen=True)
class PortfolioMetrics:
    """How hard the capital was worked."""

    capital_utilisation_pct: float
    peak_capital_utilisation_pct: float
    cash_utilisation_pct: float


@dataclass(frozen=True)
class PortfolioSeries:
    """Every curve and table the report carries."""

    equity_curve: tuple[EquityPoint, ...]
    drawdown_curve: tuple[DrawdownPoint, ...]
    daily_pnl: tuple[DailyPnlPoint, ...]
    rolling_returns: tuple[RollingReturnPoint, ...]
    monthly_returns: tuple[MonthlyReturn, ...]
    yearly_returns: tuple[YearlyReturn, ...]
    #: Bounds of the worst drawdown, for shading it on the equity chart.
    #: ``recovery_ts`` is ``None`` when the run ended still underwater.
    max_drawdown_start_ts: int | None
    max_drawdown_trough_ts: int | None
    max_drawdown_recovery_ts: int | None
    #: True when the curves above were thinned for transport.
    curves_downsampled: bool


def compute_portfolio_metrics(series: EquitySeries) -> PortfolioMetrics:
    """Average and peak share of equity deployed in positions.

    ``capital_utilisation_pct`` averages over **every** bar, including flat ones,
    so it answers "how much of the account was working, on average". A strategy
    that deploys everything but only trades a tenth of the time reads ~10% here,
    which is the honest answer for capital planning.

    ``cash_utilisation_pct`` is the complement: the average share sitting idle.
    """
    if series.is_empty:
        return PortfolioMetrics(
            capital_utilisation_pct=0.0,
            peak_capital_utilisation_pct=0.0,
            cash_utilisation_pct=100.0,
        )

    with np.errstate(divide="ignore", invalid="ignore"):
        utilisation = np.where(
            series.equity > 0.0, series.exposure_notional / series.equity * 100.0, 0.0
        )
    utilisation = np.nan_to_num(utilisation, nan=0.0, posinf=0.0, neginf=0.0)
    average = float(np.mean(utilisation))

    return PortfolioMetrics(
        capital_utilisation_pct=num.percent(average),
        peak_capital_utilisation_pct=num.percent(float(np.max(utilisation))),
        cash_utilisation_pct=num.percent(max(100.0 - average, 0.0)),
    )


def compute_rolling_returns(
    daily: DailySeries, *, window_days: int
) -> tuple[RollingReturnPoint, ...]:
    """Trailing ``window_days`` return ending on each day.

    Empty when the run is shorter than the window - a partial window would be a
    different measurement wearing the same label.
    """
    if daily.day_count <= window_days:
        return ()

    end = daily.equity[window_days:]
    start = daily.equity[:-window_days]
    with np.errstate(divide="ignore", invalid="ignore"):
        returns = np.where(start != 0.0, (end / start - 1.0) * 100.0, 0.0)
    returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)

    return tuple(
        RollingReturnPoint(day_ms=int(day_ms), return_pct=num.percent(float(value)))
        for day_ms, value in zip(daily.day_ms[window_days:].tolist(), returns.tolist(), strict=True)
    )


def compute_daily_pnl(daily: DailySeries) -> tuple[DailyPnlPoint, ...]:
    """Per-day P&L, return and closing equity."""
    return tuple(
        DailyPnlPoint(
            day_ms=int(day_ms),
            pnl=num.money(float(pnl)),
            return_pct=num.percent(float(return_pct)),
            equity=num.money(float(equity)),
        )
        for day_ms, pnl, return_pct, equity in zip(
            daily.day_ms.tolist(),
            daily.pnl.tolist(),
            daily.returns_pct.tolist(),
            daily.equity.tolist(),
            strict=True,
        )
    )


def build_portfolio_series(
    *,
    series: EquitySeries,
    drawdowns: DrawdownSeries,
    drawdown_metrics: DrawdownMetrics,
    daily: DailySeries,
    monthly_returns: tuple[MonthlyReturn, ...],
    yearly_returns: tuple[YearlyReturn, ...],
    config: AnalyticsConfig,
) -> PortfolioSeries:
    """Assemble every emitted curve, thinning the per-bar ones if needed."""
    keep = _sample_indices(series, drawdowns, limit=config.max_curve_points)

    equity_curve = tuple(
        EquityPoint(
            ts=int(series.ts[index]),
            equity=num.money(float(series.equity[index])),
            realised=num.money(float(series.realised[index])),
        )
        for index in keep
    )
    drawdown_curve = tuple(
        DrawdownPoint(
            ts=int(drawdowns.ts[index]),
            depth=num.money(float(drawdowns.depth[index])),
            depth_pct=num.percent(float(drawdowns.depth_pct[index])),
        )
        for index in keep
    )

    return PortfolioSeries(
        equity_curve=equity_curve,
        drawdown_curve=drawdown_curve,
        daily_pnl=compute_daily_pnl(daily),
        rolling_returns=compute_rolling_returns(daily, window_days=config.rolling_window_days),
        monthly_returns=monthly_returns,
        yearly_returns=yearly_returns,
        max_drawdown_start_ts=drawdown_metrics.max_drawdown_start_ts,
        max_drawdown_trough_ts=drawdown_metrics.max_drawdown_trough_ts,
        max_drawdown_recovery_ts=drawdown_metrics.max_drawdown_recovery_ts,
        curves_downsampled=len(keep) < series.bar_count,
    )


def _sample_indices(series: EquitySeries, drawdowns: DrawdownSeries, *, limit: int) -> list[int]:
    """Bar indices to emit: a uniform stride plus every landmark.

    Uniform striding alone can drop the single bar that holds the maximum
    drawdown, making the chart contradict the headline number. The landmarks -
    first and last bar, equity peak, equity trough, deepest drawdown - are
    force-included, and a sorted set keeps the result deterministic for a given
    input.
    """
    count = series.bar_count
    if count == 0:
        return []
    if count <= limit:
        return list(range(count))

    stride = int(np.ceil(count / limit))
    indices = set(range(0, count, stride))
    indices.update(
        {
            0,
            count - 1,
            int(np.argmax(series.equity)),
            int(np.argmin(series.equity)),
        }
    )
    if not drawdowns.is_empty:
        indices.add(int(np.argmax(drawdowns.depth)))
    return sorted(indices)
