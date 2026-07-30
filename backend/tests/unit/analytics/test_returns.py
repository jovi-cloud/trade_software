"""Return metrics: profit, annualisation, expectancy, profit factor."""

from __future__ import annotations

import pytest

from app.analytics.inputs import CALENDAR_DAYS_PER_YEAR
from app.analytics.metrics import analyse
from tests.unit.analytics.conftest import INITIAL, make_input, pnl_trade, trade


def test_net_profit_sums_closed_trade_pnl() -> None:
    report = analyse(
        make_input(
            trades=(
                pnl_trade(1, 100.0, entry_day=0, exit_day=1),
                pnl_trade(2, -40.0, entry_day=2, exit_day=3),
            ),
            closes=[100] * 5,
        )
    )

    assert report.returns.net_profit == 60.0
    assert report.returns.gross_profit == 100.0
    assert report.returns.gross_loss == 40.0
    assert report.returns.total_return_pct == pytest.approx(0.6)


def test_profit_factor_is_gross_profit_over_gross_loss() -> None:
    report = analyse(
        make_input(
            trades=(
                pnl_trade(1, 100.0, entry_day=0, exit_day=1),
                pnl_trade(2, -50.0, entry_day=2, exit_day=3),
            ),
            closes=[100] * 5,
        )
    )

    assert report.returns.profit_factor == 2.0


def test_profit_factor_is_undefined_without_a_losing_trade() -> None:
    """Not zero. Zero would rank a flawless run below a mediocre one."""
    report = analyse(
        make_input(trades=(pnl_trade(1, 100.0, entry_day=0, exit_day=1),), closes=[100] * 3)
    )

    assert report.returns.profit_factor is None


def test_payoff_ratio_is_average_win_over_average_loss() -> None:
    report = analyse(
        make_input(
            trades=(
                pnl_trade(1, 60.0, entry_day=0, exit_day=1),
                pnl_trade(2, 40.0, entry_day=1, exit_day=2),
                pnl_trade(3, -25.0, entry_day=2, exit_day=3),
            ),
            closes=[100] * 5,
        )
    )

    assert report.returns.average_win == 50.0
    assert report.returns.average_loss == 25.0
    assert report.returns.payoff_ratio == 2.0


def test_expectancy_equals_average_trade_by_construction() -> None:
    """The two formulas are algebraically the same quantity.

    Expectancy is ``win_rate * avg_win - loss_rate * avg_loss``, which collapses
    to ``net_profit / trades``. Both are reported because both are conventionally
    quoted; a divergence between them would mean one of the two is wrong.
    """
    report = analyse(
        make_input(
            trades=(
                pnl_trade(1, 90.0, entry_day=0, exit_day=1),
                pnl_trade(2, -30.0, entry_day=1, exit_day=2),
                pnl_trade(3, 0.0, entry_day=2, exit_day=3),
            ),
            closes=[100] * 5,
        )
    )

    assert report.returns.average_trade == pytest.approx(20.0)
    assert report.returns.expectancy == pytest.approx(report.returns.average_trade)


def test_breakeven_trades_dilute_both_win_and_loss_rate() -> None:
    report = analyse(
        make_input(
            trades=(
                pnl_trade(1, 100.0, entry_day=0, exit_day=1),
                pnl_trade(2, 0.0, entry_day=1, exit_day=2),
                pnl_trade(3, 0.0, entry_day=2, exit_day=3),
                pnl_trade(4, 0.0, entry_day=3, exit_day=4),
            ),
            closes=[100] * 6,
        )
    )

    assert report.trades.breakeven_trades == 3
    assert report.trades.win_rate_pct == 25.0
    assert report.trades.loss_rate_pct == 0.0
    # Deliberately does not sum to 100: a scratch trade is neither outcome.
    assert report.trades.win_rate_pct + report.trades.loss_rate_pct == 25.0


def test_cagr_compounds_over_elapsed_calendar_time() -> None:
    """One year of daily bars doubling the account is a 100% CAGR."""
    days = 366  # 2025-01-01 .. 2026-01-01, an elapsed year of bars
    report = analyse(
        make_input(
            trades=(
                trade(
                    1,
                    entry_day=0,
                    exit_day=days - 1,
                    entry_price=100.0,
                    exit_price=100.0 + INITIAL,
                ),
            ),
            closes=[100] * days,
        )
    )

    elapsed_years = (days - 1) / CALENDAR_DAYS_PER_YEAR
    expected = ((2.0) ** (1 / elapsed_years) - 1) * 100
    assert report.returns.cagr_pct == pytest.approx(expected, rel=1e-6)


def test_annualised_return_scales_linearly_and_differs_from_cagr() -> None:
    report = analyse(
        make_input(
            trades=(pnl_trade(1, 1_000.0, entry_day=0, exit_day=100),),
            closes=[100] * 101,
        )
    )

    # 10% over 100 elapsed days, scaled linearly to a year.
    assert report.returns.annualised_return_pct == pytest.approx(
        10.0 * CALENDAR_DAYS_PER_YEAR / 100, rel=1e-6
    )
    assert report.returns.cagr_pct != report.returns.annualised_return_pct


def test_annualisation_is_undefined_for_a_sub_day_run() -> None:
    """Annualising a few bars produces a number with no meaning."""
    report = analyse(make_input(trades=(), closes=[100]))

    assert report.returns.annualised_return_pct is None
    assert report.returns.cagr_pct is None


def test_cagr_is_undefined_when_the_account_is_wiped_out() -> None:
    report = analyse(
        make_input(
            trades=(pnl_trade(1, -INITIAL, entry_day=0, exit_day=5),),
            closes=[100] * 10,
        )
    )

    assert report.returns.cagr_pct is None
    assert report.returns.total_return_pct == -100.0


def test_recovery_factor_is_net_profit_over_max_drawdown() -> None:
    report = analyse(
        make_input(
            trades=(
                pnl_trade(1, -100.0, entry_day=0, exit_day=1),
                pnl_trade(2, 300.0, entry_day=2, exit_day=3),
            ),
            closes=[100] * 5,
        )
    )

    assert report.risk.max_drawdown == 100.0
    assert report.returns.recovery_factor == 2.0


def test_recovery_factor_is_undefined_without_a_drawdown() -> None:
    report = analyse(
        make_input(trades=(pnl_trade(1, 100.0, entry_day=0, exit_day=1),), closes=[100] * 3)
    )

    assert report.risk.max_drawdown == 0.0
    assert report.returns.recovery_factor is None


def test_costs_are_reported_and_already_deducted_from_net_profit() -> None:
    report = analyse(
        make_input(
            trades=(
                trade(
                    1,
                    entry_day=0,
                    exit_day=2,
                    entry_price=100.0,
                    exit_price=150.0,
                    commission=10.0,
                    slippage_cost=5.0,
                ),
            ),
            closes=[100] * 4,
        )
    )

    assert report.returns.commission_paid == 10.0
    assert report.returns.slippage_cost == 5.0
    assert report.returns.net_profit == 35.0
