"""Trade statistics: counts, rates, streaks, holding times, MAE and MFE."""

from __future__ import annotations

import pytest

from app.analytics.inputs import MS_PER_DAY
from app.analytics.metrics import analyse
from app.domain.enums import PositionSide
from tests.unit.analytics.conftest import make_input, pnl_trade, trade


def test_counts_split_winners_losers_and_breakeven() -> None:
    report = analyse(
        make_input(
            trades=(
                pnl_trade(1, 50.0, entry_day=0, exit_day=1),
                pnl_trade(2, -20.0, entry_day=1, exit_day=2),
                pnl_trade(3, 0.0, entry_day=2, exit_day=3),
                pnl_trade(4, 30.0, entry_day=3, exit_day=4),
            ),
            closes=[100] * 6,
        )
    )

    assert report.trades.total_trades == 4
    assert report.trades.winning_trades == 2
    assert report.trades.losing_trades == 1
    assert report.trades.breakeven_trades == 1
    assert report.trades.win_rate_pct == 50.0
    assert report.trades.loss_rate_pct == 25.0


def test_win_rate_is_zero_with_no_trades() -> None:
    report = analyse(make_input(trades=(), closes=[100] * 5))

    assert report.trades.total_trades == 0
    assert report.trades.win_rate_pct == 0.0
    assert report.trades.loss_rate_pct == 0.0


def test_all_winners_is_a_hundred_percent_win_rate() -> None:
    report = analyse(
        make_input(
            trades=(
                pnl_trade(1, 10.0, entry_day=0, exit_day=1),
                pnl_trade(2, 20.0, entry_day=1, exit_day=2),
            ),
            closes=[100] * 4,
        )
    )

    assert report.trades.win_rate_pct == 100.0
    assert report.trades.longest_win_streak == 2
    assert report.trades.longest_loss_streak == 0


def test_all_losers_is_a_hundred_percent_loss_rate() -> None:
    report = analyse(
        make_input(
            trades=(
                pnl_trade(1, -10.0, entry_day=0, exit_day=1),
                pnl_trade(2, -20.0, entry_day=1, exit_day=2),
            ),
            closes=[100] * 4,
        )
    )

    assert report.trades.loss_rate_pct == 100.0
    assert report.trades.longest_loss_streak == 2
    assert report.trades.longest_win_streak == 0


def test_streaks_take_the_longest_run_not_the_last() -> None:
    outcomes = [10.0, 10.0, 10.0, -5.0, 10.0, -5.0, -5.0, 10.0]
    report = analyse(
        make_input(
            trades=tuple(
                pnl_trade(index + 1, pnl, entry_day=index, exit_day=index + 1)
                for index, pnl in enumerate(outcomes)
            ),
            closes=[100] * (len(outcomes) + 1),
        )
    )

    assert report.trades.longest_win_streak == 3
    assert report.trades.longest_loss_streak == 2


def test_a_breakeven_trade_breaks_a_streak() -> None:
    outcomes = [10.0, 10.0, 0.0, 10.0]
    report = analyse(
        make_input(
            trades=tuple(
                pnl_trade(index + 1, pnl, entry_day=index, exit_day=index + 1)
                for index, pnl in enumerate(outcomes)
            ),
            closes=[100] * (len(outcomes) + 1),
        )
    )

    assert report.trades.longest_win_streak == 2


def test_holding_times_are_reported_in_milliseconds() -> None:
    report = analyse(
        make_input(
            trades=(
                trade(1, entry_day=0, exit_day=1, entry_price=100.0, exit_price=100.0),
                trade(2, entry_day=2, exit_day=7, entry_price=100.0, exit_price=100.0),
            ),
            closes=[100] * 10,
        )
    )

    assert report.trades.min_holding_time_ms == MS_PER_DAY
    assert report.trades.max_holding_time_ms == 5 * MS_PER_DAY
    assert report.trades.average_holding_time_ms == 3 * MS_PER_DAY
    assert report.trades.average_bars_held == 3.0


def test_largest_winner_and_loser_are_the_single_extremes() -> None:
    report = analyse(
        make_input(
            trades=(
                pnl_trade(1, 500.0, entry_day=0, exit_day=1),
                pnl_trade(2, -300.0, entry_day=1, exit_day=2),
                pnl_trade(3, 100.0, entry_day=2, exit_day=3),
            ),
            closes=[100] * 5,
        )
    )

    assert report.trades.largest_winner == 500.0
    # Reported as a positive magnitude.
    assert report.trades.largest_loser == 300.0


def test_long_excursions_measure_against_bar_extremes() -> None:
    """Bars 0..3 span the trade; highs are close+1 and lows close-1."""
    report = analyse(
        make_input(
            trades=(
                trade(
                    1, entry_day=0, exit_day=3, entry_price=100.0, exit_price=120.0, quantity=2.0
                ),
            ),
            closes=[100, 130, 90, 120],
        )
    )

    # Best high is 131 (bar 1), worst low is 89 (bar 2), entry 100, 2 units.
    assert report.trades.average_mfe == pytest.approx(31.0 * 2)
    assert report.trades.average_mae == pytest.approx(11.0 * 2)


def test_short_excursions_invert_favourable_and_adverse() -> None:
    report = analyse(
        make_input(
            trades=(
                trade(
                    1,
                    entry_day=0,
                    exit_day=3,
                    entry_price=100.0,
                    exit_price=90.0,
                    side=PositionSide.SHORT,
                ),
            ),
            closes=[100, 130, 90, 90],
        )
    )

    # For a short, a fall is favourable: low 89 gives an 11 MFE; high 131 gives
    # a 31 MAE.
    assert report.trades.average_mfe == pytest.approx(11.0)
    assert report.trades.average_mae == pytest.approx(31.0)


def test_excursions_are_undefined_without_bars() -> None:
    """A report built from trades alone cannot know intra-trade prices."""
    report = analyse(make_input(trades=(pnl_trade(1, 10.0, entry_day=0, exit_day=1),), closes=[]))

    assert report.trades.average_mae is None
    assert report.trades.average_mfe is None
    assert report.statistics.edge_ratio is None
