"""Sharpe, Sortino, Calmar, MAR, Information and Treynor ratios."""

from __future__ import annotations

import numpy as np
import pytest

from app.analytics.inputs import TRADING_DAYS_PER_YEAR, AnalyticsConfig
from app.analytics.metrics import analyse
from app.analytics.report import AnalyticsReport
from tests.unit.analytics.conftest import make_input, pnl_trade

ANNUALISATION = float(np.sqrt(TRADING_DAYS_PER_YEAR))
DAILY_PNL = [200.0, -100.0, 300.0, -50.0, 150.0, -200.0, 400.0, 100.0]


def _run(daily_pnl: list[float], config: AnalyticsConfig | None = None) -> AnalyticsReport:
    return analyse(
        make_input(
            trades=tuple(
                pnl_trade(index + 1, pnl, entry_day=index, exit_day=index + 1)
                for index, pnl in enumerate(daily_pnl)
            ),
            closes=[100] * (len(daily_pnl) + 1),
            config=config,
        )
    )


def test_sharpe_is_mean_excess_over_stdev_annualised() -> None:
    report = _run(DAILY_PNL)
    returns = np.array([point.return_pct for point in report.series.daily_pnl], dtype=np.float64)

    expected = float(np.mean(returns)) / float(np.std(returns, ddof=1)) * ANNUALISATION
    assert report.risk_adjusted.sharpe_ratio == pytest.approx(expected, rel=1e-4)


def test_a_risk_free_rate_lowers_sharpe() -> None:
    """The hurdle is subtracted from every daily return before averaging."""
    without = _run(DAILY_PNL)
    with_hurdle = _run(DAILY_PNL, AnalyticsConfig(risk_free_rate_pct=6.0))

    assert without.risk_adjusted.sharpe_ratio is not None
    assert with_hurdle.risk_adjusted.sharpe_ratio is not None
    assert with_hurdle.risk_adjusted.sharpe_ratio < without.risk_adjusted.sharpe_ratio
    assert with_hurdle.meta.risk_free_rate_pct == 6.0


def test_sortino_exceeds_sharpe_when_upside_dominates() -> None:
    """Ignoring upside volatility can only help a strategy with big up days."""
    report = _run([500.0, -50.0, 600.0, -40.0, 700.0, -30.0])

    assert report.risk_adjusted.sharpe_ratio is not None
    assert report.risk_adjusted.sortino_ratio is not None
    assert report.risk_adjusted.sortino_ratio > report.risk_adjusted.sharpe_ratio


def test_calmar_is_annualised_return_over_max_drawdown_pct() -> None:
    report = _run(DAILY_PNL)

    assert report.returns.annualised_return_pct is not None
    assert report.risk_adjusted.calmar_ratio == pytest.approx(
        report.returns.annualised_return_pct / report.risk.max_drawdown_pct, rel=1e-4
    )


def test_mar_uses_cagr_where_calmar_uses_the_linear_annualisation() -> None:
    report = _run(DAILY_PNL)

    assert report.returns.cagr_pct is not None
    assert report.risk_adjusted.mar_ratio == pytest.approx(
        report.returns.cagr_pct / report.risk.max_drawdown_pct, rel=1e-4
    )
    assert report.risk_adjusted.mar_ratio != report.risk_adjusted.calmar_ratio


def test_calmar_and_mar_are_undefined_without_a_drawdown() -> None:
    report = _run([100.0, 200.0, 300.0])

    assert report.risk.max_drawdown_pct == 0.0
    assert report.risk_adjusted.calmar_ratio is None
    assert report.risk_adjusted.mar_ratio is None


def test_information_ratio_needs_a_benchmark() -> None:
    report = _run(DAILY_PNL)

    assert report.risk_adjusted.information_ratio is None


def test_information_ratio_is_computed_against_an_aligned_benchmark() -> None:
    report = _run(DAILY_PNL)
    days = report.meta.trading_days
    benchmark = tuple(0.1 for _ in range(days))

    with_benchmark = _run(DAILY_PNL, AnalyticsConfig(benchmark_daily_returns_pct=benchmark))

    assert with_benchmark.risk_adjusted.information_ratio is not None


def test_a_misaligned_benchmark_is_refused_rather_than_truncated() -> None:
    """A silently truncated comparison is worse than an absent one."""
    report = _run(DAILY_PNL, AnalyticsConfig(benchmark_daily_returns_pct=(0.1, 0.2)))

    assert report.meta.trading_days != 2
    assert report.risk_adjusted.information_ratio is None


def test_treynor_stays_undefined_until_a_beta_is_supplied() -> None:
    without = _run(DAILY_PNL)
    with_beta = _run(DAILY_PNL, AnalyticsConfig(beta=1.2, risk_free_rate_pct=6.0))

    assert without.risk_adjusted.treynor_ratio is None
    assert with_beta.returns.annualised_return_pct is not None
    assert with_beta.risk_adjusted.treynor_ratio == pytest.approx(
        (with_beta.returns.annualised_return_pct - 6.0) / 1.2, rel=1e-4
    )


def test_a_losing_strategy_reports_a_negative_sharpe() -> None:
    report = _run([-100.0, -200.0, 50.0, -150.0, -100.0])

    assert report.risk_adjusted.sharpe_ratio is not None
    assert report.risk_adjusted.sharpe_ratio < 0
    assert report.returns.net_profit < 0
