"""Risk-adjusted return ratios.

Sharpe and Sortino are computed from the daily excess-return series and
annualised with ``sqrt(252)``. Calmar and MAR divide an annualised return by the
maximum drawdown, so they are annualised by construction and are *not* scaled
again.

Every ratio here is ``float | None``. A ratio whose denominator is zero - a flat
equity curve has no volatility, a run that never lost has no drawdown - is
undefined, and reporting it as ``0.0`` would rank a perfect strategy below a
mediocre one.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.analytics import _numeric as num
from app.analytics.inputs import AnalyticsConfig
from app.analytics.risk import ANNUALISATION, DispersionBasis


@dataclass(frozen=True)
class RiskAdjustedMetrics:
    """Return per unit of risk, by four different definitions of risk."""

    sharpe_ratio: float | None
    sortino_ratio: float | None
    calmar_ratio: float | None
    mar_ratio: float | None
    information_ratio: float | None
    treynor_ratio: float | None


def compute_risk_adjusted_metrics(
    *,
    dispersion: DispersionBasis,
    annualised_return_pct: float | None,
    cagr_pct: float | None,
    max_drawdown_pct: float,
    config: AnalyticsConfig,
) -> RiskAdjustedMetrics:
    """Assemble the risk-adjusted group.

    Reuses the dispersion terms computed for the risk group - the standard
    deviation is never calculated twice.
    """
    mean_excess = num.mean(dispersion.excess_returns_pct)

    sharpe = (
        None
        if dispersion.daily_stdev_pct is None
        else num.divide(mean_excess, dispersion.daily_stdev_pct)
    )
    sortino = (
        None
        if dispersion.daily_downside_deviation_pct is None
        else num.divide(mean_excess, dispersion.daily_downside_deviation_pct)
    )

    return RiskAdjustedMetrics(
        sharpe_ratio=num.ratio(None if sharpe is None else sharpe * ANNUALISATION),
        sortino_ratio=num.ratio(None if sortino is None else sortino * ANNUALISATION),
        calmar_ratio=(
            None
            if annualised_return_pct is None
            else num.ratio(num.divide(annualised_return_pct, max_drawdown_pct))
        ),
        mar_ratio=(None if cagr_pct is None else num.ratio(num.divide(cagr_pct, max_drawdown_pct))),
        information_ratio=_information_ratio(dispersion, config),
        treynor_ratio=_treynor_ratio(annualised_return_pct, config),
    )


def _information_ratio(dispersion: DispersionBasis, config: AnalyticsConfig) -> float | None:
    """Active return over tracking error, against a supplied benchmark.

    ``None`` until a benchmark series is provided. The benchmark must be aligned
    to the run's trading days, one value per day, in percent; a length mismatch
    is treated as no benchmark rather than silently truncated, because a
    misaligned comparison is worse than an absent one.
    """
    benchmark = config.benchmark_daily_returns_pct
    if not benchmark:
        return None
    # excess is already net of the risk-free rate; add it back to compare like
    # with like against a raw benchmark return series.
    portfolio = dispersion.excess_returns_pct + config.daily_risk_free_pct
    if len(benchmark) != portfolio.size:
        return None
    active = portfolio - np.asarray(benchmark, dtype=np.float64)
    tracking_error = num.sample_stdev(active)
    if tracking_error is None:
        return None
    daily_ratio = num.divide(num.mean(active), tracking_error)
    if daily_ratio is None:
        return None
    return num.ratio(daily_ratio * ANNUALISATION)


def _treynor_ratio(annualised_return_pct: float | None, config: AnalyticsConfig) -> float | None:
    """Excess annualised return per unit of market beta.

    Future-ready: beta needs a benchmark price series the platform does not
    ingest yet, so this stays ``None`` until ``AnalyticsConfig.beta`` is
    supplied. The formula is here so adding benchmarks later is a data change,
    not a metrics change.
    """
    if config.beta is None or annualised_return_pct is None:
        return None
    return num.ratio(num.divide(annualised_return_pct - config.risk_free_rate_pct, config.beta))
