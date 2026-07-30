"""Risk metrics: volatility, tail loss, exposure and time in market."""

from __future__ import annotations

import numpy as np
import pytest

from app.analytics.inputs import TRADING_DAYS_PER_YEAR, AnalyticsConfig, AnalyticsInput
from app.analytics.metrics import analyse
from app.domain.enums import PositionSide
from tests.unit.analytics.conftest import INITIAL, make_input, pnl_trade, trade

ANNUALISATION = float(np.sqrt(TRADING_DAYS_PER_YEAR))


def _daily_returns_run(daily_pnl: list[float]) -> AnalyticsInput:
    """One trade per day, so each day's return is exactly its P&L over equity."""
    return make_input(
        trades=tuple(
            pnl_trade(index + 1, pnl, entry_day=index, exit_day=index + 1)
            for index, pnl in enumerate(daily_pnl)
        ),
        closes=[100] * (len(daily_pnl) + 1),
    )


def test_volatility_is_the_sample_stdev_of_daily_returns() -> None:
    report = analyse(_daily_returns_run([100.0, -100.0, 100.0, -100.0]))
    daily = report.series.daily_pnl

    returns = np.array([point.return_pct for point in daily], dtype=np.float64)
    assert report.risk.volatility_pct == pytest.approx(float(np.std(returns, ddof=1)), rel=1e-6)


def test_annualised_volatility_scales_daily_by_sqrt_252() -> None:
    report = analyse(_daily_returns_run([100.0, -50.0, 75.0, -25.0, 60.0]))

    assert report.risk.volatility_pct is not None
    assert report.risk.annualised_volatility_pct == pytest.approx(
        report.risk.volatility_pct * ANNUALISATION, rel=1e-4
    )


def test_zero_volatility_is_undefined_not_zero() -> None:
    """A flat curve has no dispersion, and dividing by it must not yield 0."""
    report = analyse(make_input(trades=(), closes=[100] * 10))

    assert report.risk.volatility_pct is None
    assert report.risk.annualised_volatility_pct is None
    assert report.risk.downside_deviation_pct is None
    assert report.risk_adjusted.sharpe_ratio is None
    assert report.risk_adjusted.sortino_ratio is None


def test_downside_deviation_is_below_total_volatility_when_there_is_upside() -> None:
    """Only shortfalls enter the numerator, so it cannot exceed total dispersion."""
    report = analyse(_daily_returns_run([300.0, -100.0, 400.0, -50.0, 250.0]))

    assert report.risk.downside_deviation_pct is not None
    assert report.risk.annualised_volatility_pct is not None
    assert report.risk.downside_deviation_pct < report.risk.annualised_volatility_pct


def test_downside_deviation_is_undefined_when_no_day_lost_money() -> None:
    """No shortfall means no downside risk to divide by - hence no Sortino."""
    report = analyse(_daily_returns_run([100.0, 200.0, 50.0, 300.0]))

    assert report.risk.downside_deviation_pct is None
    assert report.risk_adjusted.sortino_ratio is None
    # Total volatility still exists: the gains were uneven.
    assert report.risk.annualised_volatility_pct is not None


def test_value_at_risk_is_the_empirical_percentile_of_daily_returns() -> None:
    report = analyse(_daily_returns_run([100.0, -200.0, 50.0, -50.0, 25.0, -25.0, 10.0, 300.0]))

    returns = np.array([point.return_pct for point in report.series.daily_pnl], dtype=np.float64)
    assert report.risk.value_at_risk_pct == pytest.approx(
        -float(np.percentile(returns, 5.0)), rel=1e-4
    )


def test_conditional_var_averages_the_tail_beyond_var() -> None:
    report = analyse(
        _daily_returns_run([-500.0, -400.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0]),
    )

    assert report.risk.value_at_risk_pct is not None
    assert report.risk.conditional_value_at_risk_pct is not None
    # The expected shortfall averages the worst days, so it is at least as bad
    # as the VaR threshold itself.
    assert report.risk.conditional_value_at_risk_pct >= report.risk.value_at_risk_pct


def test_var_confidence_level_is_configurable_and_recorded() -> None:
    pnl = [100.0, -200.0, 50.0, -50.0, 25.0, -25.0, 10.0, 300.0]
    data = _daily_returns_run(pnl)
    strict = analyse(
        make_input(
            trades=data.trades,
            closes=[100] * (len(pnl) + 1),
            config=AnalyticsConfig(var_confidence_pct=99.0),
        )
    )

    assert strict.meta.var_confidence_pct == 99.0
    assert strict.risk.value_at_risk_pct is not None


def test_var_is_undefined_with_fewer_than_two_days() -> None:
    report = analyse(make_input(trades=(), closes=[100]))

    assert report.risk.value_at_risk_pct is None
    assert report.risk.conditional_value_at_risk_pct is None


def test_exposure_counts_bars_holding_a_position() -> None:
    report = analyse(
        make_input(
            trades=(trade(1, entry_day=0, exit_day=4, entry_price=100.0, exit_price=100.0),),
            closes=[100] * 10,
        )
    )

    # In position on bars 0..3 of 10.
    assert report.risk.exposure_pct == 40.0


def test_time_in_market_uses_calendar_time_not_bar_count() -> None:
    """Bar-weighted and time-weighted exposure differ once bars are sparse."""
    report = analyse(
        make_input(
            trades=(trade(1, entry_day=0, exit_day=4, entry_price=100.0, exit_price=100.0),),
            closes=[100] * 10,
        )
    )

    # Held 4 of the 9 elapsed days.
    assert report.risk.time_in_market_pct == pytest.approx(4 / 9 * 100, rel=1e-6)
    assert report.risk.time_in_market_pct != report.risk.exposure_pct


def test_a_run_with_no_trades_has_no_exposure() -> None:
    report = analyse(make_input(trades=(), closes=[100] * 10))

    assert report.risk.exposure_pct == 0.0
    assert report.risk.time_in_market_pct == 0.0


def test_short_trades_contribute_exposure_the_same_way() -> None:
    report = analyse(
        make_input(
            trades=(
                trade(
                    1,
                    entry_day=0,
                    exit_day=5,
                    entry_price=100.0,
                    exit_price=90.0,
                    side=PositionSide.SHORT,
                ),
            ),
            closes=[100] * 10,
        )
    )

    assert report.risk.exposure_pct == 50.0
    assert report.returns.net_profit == 10.0


def test_capital_utilisation_averages_over_every_bar() -> None:
    report = analyse(
        make_input(
            trades=(
                trade(
                    1,
                    entry_day=0,
                    exit_day=1,
                    entry_price=100.0,
                    exit_price=100.0,
                    quantity=INITIAL / 100,
                ),
            ),
            closes=[100] * 10,
        )
    )

    # Fully deployed on bar 0 only: 100% for one bar out of ten.
    assert report.portfolio.peak_capital_utilisation_pct == 100.0
    assert report.portfolio.capital_utilisation_pct == 10.0
    assert report.portfolio.cash_utilisation_pct == 90.0
