"""Degenerate inputs. A report must always exist and never carry a fake number.

The rule these tests enforce: a metric that cannot be measured is ``None``, a
metric that genuinely is zero is ``0.0``, and nothing is ever NaN or infinity -
the API contract could not carry either.
"""

from __future__ import annotations

import math

import pytest

from app.analytics.inputs import AnalyticsConfig, AnalyticsInput
from app.analytics.metrics import analyse
from app.analytics.report import AnalyticsReport
from tests.unit.analytics.conftest import INITIAL, make_input, pnl_trade, trade


def _all_values(report: AnalyticsReport) -> dict[str, float | None]:
    return {value.key: value.value for value in report.metric_values()}


def test_no_trades_and_no_bars() -> None:
    report = analyse(AnalyticsInput(initial_capital=INITIAL))

    assert report.returns.net_profit == 0.0
    assert report.returns.total_return_pct == 0.0
    assert report.returns.final_equity == INITIAL
    assert report.trades.total_trades == 0
    assert report.risk.max_drawdown == 0.0
    assert report.risk.exposure_pct == 0.0
    assert report.series.equity_curve == ()
    assert report.series.drawdown_curve == ()
    assert report.meta.bar_count == 0


def test_no_trades_with_bars_reports_a_flat_curve() -> None:
    report = analyse(make_input(trades=(), closes=[100] * 10))

    assert len(report.series.equity_curve) == 10
    assert {point.equity for point in report.series.equity_curve} == {INITIAL}
    assert report.risk.max_drawdown_pct == 0.0
    assert report.portfolio.capital_utilisation_pct == 0.0
    assert report.portfolio.cash_utilisation_pct == 100.0


def test_a_single_trade() -> None:
    report = analyse(
        make_input(trades=(pnl_trade(1, 250.0, entry_day=0, exit_day=3),), closes=[100] * 5)
    )

    assert report.trades.total_trades == 1
    assert report.trades.win_rate_pct == 100.0
    assert report.returns.net_profit == 250.0
    assert report.returns.average_trade == 250.0
    # A single observation has no sample standard deviation.
    assert report.statistics.sqn is None


def test_all_winners_leaves_loss_side_metrics_at_zero_or_none() -> None:
    report = analyse(
        make_input(
            trades=(
                pnl_trade(1, 100.0, entry_day=0, exit_day=1),
                pnl_trade(2, 200.0, entry_day=1, exit_day=2),
            ),
            closes=[100] * 4,
        )
    )

    assert report.returns.gross_loss == 0.0
    assert report.returns.average_loss == 0.0
    assert report.trades.losing_trades == 0
    assert report.trades.largest_loser == 0.0
    # No denominator, so these are unmeasurable rather than zero.
    assert report.returns.profit_factor is None
    assert report.returns.payoff_ratio is None
    assert report.risk_adjusted.calmar_ratio is None


def test_all_losers() -> None:
    report = analyse(
        make_input(
            trades=(
                pnl_trade(1, -100.0, entry_day=0, exit_day=1),
                pnl_trade(2, -200.0, entry_day=1, exit_day=2),
            ),
            closes=[100] * 4,
        )
    )

    assert report.returns.gross_profit == 0.0
    assert report.returns.profit_factor == 0.0  # zero profit over a real loss
    assert report.trades.win_rate_pct == 0.0
    assert report.trades.loss_rate_pct == 100.0
    assert report.returns.net_profit == -300.0
    assert report.risk.max_drawdown == 300.0
    assert report.returns.recovery_factor == -1.0


def test_flat_equity_has_no_dispersion_and_no_ratios() -> None:
    report = analyse(make_input(trades=(), closes=[100] * 30))

    assert report.risk.volatility_pct is None
    assert report.risk.annualised_volatility_pct is None
    assert report.risk.downside_deviation_pct is None
    assert report.risk_adjusted.sharpe_ratio is None
    assert report.risk_adjusted.sortino_ratio is None
    assert report.risk.value_at_risk_pct == 0.0  # every day returned exactly 0%
    assert report.risk.ulcer_index == 0.0


def test_a_wholly_negative_run_reports_negative_returns() -> None:
    report = analyse(
        make_input(
            trades=tuple(
                pnl_trade(index + 1, -50.0, entry_day=index, exit_day=index + 1)
                for index in range(20)
            ),
            closes=[100] * 21,
        )
    )

    assert report.returns.net_profit == -1_000.0
    assert report.returns.total_return_pct == -10.0
    assert report.returns.cagr_pct is not None
    assert report.returns.cagr_pct < 0
    assert report.risk_adjusted.sharpe_ratio is not None
    assert report.risk_adjusted.sharpe_ratio < 0
    assert report.risk.max_drawdown == 1_000.0


def test_a_total_wipeout_does_not_produce_infinities() -> None:
    report = analyse(
        make_input(trades=(pnl_trade(1, -INITIAL, entry_day=0, exit_day=5),), closes=[100] * 10)
    )

    assert report.returns.final_equity == 0.0
    assert report.returns.total_return_pct == -100.0
    assert report.risk.max_drawdown_pct == 100.0
    assert report.returns.cagr_pct is None


def test_no_metric_is_ever_nan_or_infinite() -> None:
    """JSON cannot represent either, so the report must never produce one."""
    scenarios = [
        AnalyticsInput(initial_capital=INITIAL),
        make_input(trades=(), closes=[100] * 5),
        make_input(trades=(pnl_trade(1, 0.0, entry_day=0, exit_day=1),), closes=[100] * 3),
        make_input(trades=(pnl_trade(1, -INITIAL, entry_day=0, exit_day=1),), closes=[100] * 3),
        make_input(
            trades=(pnl_trade(1, 1e12, entry_day=0, exit_day=1),),
            closes=[100] * 3,
        ),
    ]

    for data in scenarios:
        for key, value in _all_values(analyse(data)).items():
            assert value is None or math.isfinite(value), f"{key} is not finite"


def test_zero_initial_capital_does_not_divide_by_zero() -> None:
    report = analyse(make_input(trades=(), closes=[100] * 5, initial_capital=0.0))

    assert report.returns.total_return_pct == 0.0
    assert report.returns.cagr_pct is None
    assert report.risk.max_drawdown_pct == 0.0


def test_a_breakeven_only_run() -> None:
    report = analyse(
        make_input(
            trades=(
                pnl_trade(1, 0.0, entry_day=0, exit_day=1),
                pnl_trade(2, 0.0, entry_day=1, exit_day=2),
            ),
            closes=[100] * 4,
        )
    )

    assert report.trades.breakeven_trades == 2
    assert report.trades.win_rate_pct == 0.0
    assert report.trades.loss_rate_pct == 0.0
    assert report.returns.profit_factor is None
    assert report.returns.net_profit == 0.0


def test_a_trade_entirely_outside_the_bar_range_is_ignored_for_marking() -> None:
    """Defensive: a trade whose window contains no bar cannot mark to market."""
    report = analyse(
        make_input(trades=(pnl_trade(1, 100.0, entry_day=50, exit_day=60),), closes=[100] * 5)
    )

    # It still counts as a realised trade; it just never appears as exposure.
    assert report.trades.total_trades == 1
    assert report.risk.exposure_pct == 0.0
    assert report.trades.average_mae is None


def test_rolling_returns_need_a_full_window() -> None:
    short = analyse(make_input(trades=(), closes=[100] * 10))
    long_enough = analyse(make_input(trades=(), closes=[100] * 40))

    assert short.series.rolling_returns == ()
    assert len(long_enough.series.rolling_returns) == 40 - 21


def test_curves_are_capped_and_keep_their_extremes() -> None:
    """Downsampling must never let a chart contradict a headline number."""
    bars_count = 500
    report = analyse(
        make_input(
            trades=(
                trade(
                    1,
                    entry_day=0,
                    exit_day=bars_count - 1,
                    entry_price=100.0,
                    exit_price=100.0,
                    quantity=1.0,
                ),
            ),
            closes=[100.0 - (index % 50) for index in range(bars_count)],
            config=AnalyticsConfig(max_curve_points=50),
        )
    )

    assert report.series.curves_downsampled is True
    assert len(report.series.equity_curve) <= 60  # stride plus forced landmarks
    worst_emitted = max(point.depth for point in report.series.drawdown_curve)
    assert worst_emitted == pytest.approx(report.risk.max_drawdown, abs=5e-7)


def test_curves_are_not_thinned_when_they_fit() -> None:
    report = analyse(make_input(trades=(), closes=[100] * 100))

    assert report.series.curves_downsampled is False
    assert len(report.series.equity_curve) == 100
