"""Drawdown: depth, episodes, duration and the Ulcer Index."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.analytics.drawdown import (
    DrawdownSeries,
    build_drawdown_series,
    compute_drawdown_metrics,
)
from app.analytics.equity import build_equity_series
from app.analytics.inputs import MS_PER_DAY, TradeRecord
from app.analytics.metrics import analyse
from tests.unit.analytics.conftest import INITIAL, bars, make_input, pnl_trade, trade, ts_at


def _drawdowns(closes: Sequence[float], trades: tuple[TradeRecord, ...] = ()) -> DrawdownSeries:
    series = build_equity_series(bars=bars(closes), trades=trades, initial_capital=INITIAL)
    return build_drawdown_series(series)


def test_flat_equity_never_goes_underwater() -> None:
    metrics = compute_drawdown_metrics(_drawdowns([100] * 5))

    assert metrics.max_drawdown == 0.0
    assert metrics.max_drawdown_pct == 0.0
    assert metrics.drawdown_episodes == 0
    assert metrics.longest_drawdown_ms == 0
    assert metrics.ulcer_index == 0.0


def test_drawdown_is_measured_from_the_running_peak() -> None:
    """Peak 10,100 then trough 10,050 is a 50 drawdown, not 50 off the start."""
    report = analyse(
        make_input(
            trades=(
                pnl_trade(1, 100.0, entry_day=0, exit_day=1),
                pnl_trade(2, -50.0, entry_day=1, exit_day=2),
            ),
            closes=[100] * 4,
        )
    )

    assert report.risk.max_drawdown == 50.0
    assert report.risk.max_drawdown_pct == pytest.approx(50 / 10_100 * 100, rel=1e-6)


def test_starting_capital_seeds_the_peak() -> None:
    """A run that loses from the first bar is in drawdown, not at a new high."""
    report = analyse(
        make_input(trades=(pnl_trade(1, -200.0, entry_day=0, exit_day=1),), closes=[100] * 3)
    )

    assert report.risk.max_drawdown == 200.0
    assert report.risk.max_drawdown_pct == 2.0


def test_average_drawdown_averages_episode_depths_not_bar_depths() -> None:
    """Two episodes of 100 and 300 average to 200, however long each lasted."""
    report = analyse(
        make_input(
            trades=(
                pnl_trade(1, -100.0, entry_day=0, exit_day=1),
                pnl_trade(2, 100.0, entry_day=1, exit_day=2),
                pnl_trade(3, -300.0, entry_day=3, exit_day=4),
                pnl_trade(4, 300.0, entry_day=5, exit_day=9),
            ),
            closes=[100] * 12,
        )
    )

    assert report.risk.drawdown_episodes == 2
    assert report.risk.max_drawdown == 300.0
    assert report.risk.average_drawdown == 200.0


def test_longest_drawdown_reports_one_episode_in_both_units() -> None:
    drawdowns = _drawdowns(
        [100] * 8,
        (
            pnl_trade(1, -100.0, entry_day=0, exit_day=1),
            pnl_trade(2, 100.0, entry_day=4, exit_day=5),
        ),
    )
    metrics = compute_drawdown_metrics(drawdowns)

    episode = drawdowns.episodes[0]
    # Underwater on bars 1..4, recovering on bar 5.
    assert episode.bars == 4
    assert metrics.longest_drawdown_bars == episode.bars
    assert metrics.longest_drawdown_ms == episode.duration_ms


def test_episode_records_its_peak_trough_and_recovery() -> None:
    drawdowns = _drawdowns(
        [100] * 6,
        (
            pnl_trade(1, 500.0, entry_day=0, exit_day=1),
            pnl_trade(2, -200.0, entry_day=1, exit_day=2),
            pnl_trade(3, 300.0, entry_day=3, exit_day=4),
        ),
    )
    episode = drawdowns.episodes[0]

    # Peak on bar 1 (10,500), trough on bar 2 (10,300), recovered on bar 4.
    assert episode.start_ts == ts_at(1)
    assert episode.trough_ts == ts_at(2)
    assert episode.recovery_ts == ts_at(4)
    assert episode.duration_ms == 3 * MS_PER_DAY


def test_an_unrecovered_drawdown_has_no_recovery_timestamp() -> None:
    drawdowns = _drawdowns(
        [100] * 4,
        (
            pnl_trade(1, 500.0, entry_day=0, exit_day=1),
            pnl_trade(2, -200.0, entry_day=1, exit_day=2),
        ),
    )
    metrics = compute_drawdown_metrics(drawdowns)

    assert drawdowns.episodes[0].recovery_ts is None
    assert metrics.max_drawdown_recovery_ts is None
    assert metrics.max_drawdown_trough_ts == ts_at(2)


def test_ulcer_index_is_the_rms_of_percentage_drawdown() -> None:
    """Averaged over every bar, including the ones at a new high."""
    drawdowns = _drawdowns(
        [100] * 4,
        (
            pnl_trade(1, -100.0, entry_day=0, exit_day=1),
            pnl_trade(2, 100.0, entry_day=1, exit_day=2),
        ),
    )
    metrics = compute_drawdown_metrics(drawdowns)

    # Only bar 1 is underwater, by 100/10,000 = 1%. sqrt(1 * 1**2 / 4) = 0.5.
    assert drawdowns.depth_pct.tolist() == pytest.approx([0.0, 1.0, 0.0, 0.0])
    assert metrics.ulcer_index == pytest.approx(0.5, rel=1e-6)


def test_unrealised_losses_inside_a_trade_count_as_drawdown() -> None:
    """A trade that ends up profitable can still produce the worst drawdown."""
    report = analyse(
        make_input(
            trades=(
                trade(
                    1, entry_day=0, exit_day=3, entry_price=100.0, exit_price=110.0, quantity=10.0
                ),
            ),
            closes=[100, 80, 90, 110],
        )
    )

    # Bar 1 marks 10 units at 80 against a 100 entry: 200 below the peak.
    assert report.risk.max_drawdown == 200.0
    assert report.returns.net_profit == 100.0
