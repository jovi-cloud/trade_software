"""Equity curve reconstruction - the series every other metric reads."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.analytics.equity import EquitySeries, build_daily_series, build_equity_series
from app.analytics.inputs import MS_PER_DAY, BarRecord, TradeRecord
from app.domain.enums import PositionSide
from tests.unit.analytics.conftest import INITIAL, bars, trade, ts_at


def _series(closes: Sequence[float], trades: tuple[TradeRecord, ...] = ()) -> EquitySeries:
    return build_equity_series(bars=bars(closes), trades=trades, initial_capital=INITIAL)


def test_flat_equity_before_any_trade_closes() -> None:
    series = _series(
        [100, 110, 120],
        (trade(1, entry_day=0, exit_day=2, entry_price=100.0, exit_price=120.0),),
    )

    # Realised P&L only lands on the exit bar; before that the position is
    # marked to market against the close.
    assert series.realised.tolist() == [INITIAL, INITIAL, INITIAL + 20.0]
    assert series.equity.tolist() == [INITIAL, INITIAL + 10.0, INITIAL + 20.0]


def test_long_position_marks_to_market_against_close() -> None:
    series = _series(
        [100, 90, 95],
        (trade(1, entry_day=0, exit_day=2, entry_price=100.0, exit_price=95.0),),
    )

    assert series.equity.tolist() == [INITIAL, INITIAL - 10.0, INITIAL - 5.0]


def test_short_position_gains_when_price_falls() -> None:
    series = _series(
        [100, 90, 80],
        (
            trade(
                1,
                entry_day=0,
                exit_day=2,
                entry_price=100.0,
                exit_price=80.0,
                side=PositionSide.SHORT,
            ),
        ),
    )

    assert series.equity.tolist() == [INITIAL, INITIAL + 10.0, INITIAL + 20.0]


def test_position_is_not_held_through_the_exit_bar() -> None:
    """The exit fills at the exit bar's open, so that bar is already flat."""
    series = _series(
        [100, 110, 120, 130],
        (trade(1, entry_day=0, exit_day=2, entry_price=100.0, exit_price=120.0),),
    )

    assert series.in_position.tolist() == [True, True, False, False]
    assert series.bars_in_position == 2


def test_exposure_notional_tracks_the_open_position() -> None:
    series = _series(
        [100, 110, 120],
        (trade(1, entry_day=0, exit_day=2, entry_price=100.0, exit_price=120.0, quantity=3.0),),
    )

    assert series.exposure_notional.tolist() == [300.0, 330.0, 0.0]


def test_no_bars_yields_an_empty_series() -> None:
    series = build_equity_series(bars=(), trades=(), initial_capital=INITIAL)

    assert series.is_empty
    assert series.final_equity == INITIAL
    assert series.elapsed_ms == 0
    assert series.start_ts is None


def test_trades_out_of_exit_order_still_accumulate_correctly() -> None:
    """Realised P&L is accumulated by exit time, not by list order."""
    later = trade(1, entry_day=4, exit_day=6, entry_price=100.0, exit_price=110.0)
    earlier = trade(2, entry_day=0, exit_day=2, entry_price=100.0, exit_price=105.0)

    series = _series([100] * 7, (later, earlier))

    assert series.realised.tolist() == [
        INITIAL,
        INITIAL,
        INITIAL + 5.0,
        INITIAL + 5.0,
        INITIAL + 5.0,
        INITIAL + 5.0,
        INITIAL + 15.0,
    ]


def test_elapsed_time_spans_first_to_last_bar() -> None:
    series = _series([100, 101, 102, 103])

    assert series.elapsed_ms == 3 * MS_PER_DAY
    assert series.start_ts == ts_at(0)
    assert series.end_ts == ts_at(3)


def test_daily_series_takes_the_last_bar_of_each_day() -> None:
    """Several intraday bars collapse to one closing equity for that UTC day."""
    intraday = tuple(
        BarRecord(
            ts=ts_at(0) + hour * 3_600_000,
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1.0,
        )
        for hour in range(6)
    )
    series = build_equity_series(bars=intraday, trades=(), initial_capital=INITIAL)
    daily = build_daily_series(series)

    assert series.bar_count == 6
    assert daily.day_count == 1
    assert daily.equity.tolist() == [INITIAL]


def test_first_daily_return_is_measured_against_starting_capital() -> None:
    series = _series(
        [100, 100],
        (trade(1, entry_day=0, exit_day=1, entry_price=100.0, exit_price=200.0),),
    )
    daily = build_daily_series(series)

    # Day 0 closes flat, day 1 realises +100 on 10,000.
    assert daily.returns_pct.tolist() == pytest.approx([0.0, 1.0])
    assert daily.pnl.tolist() == [0.0, 100.0]


def test_daily_series_of_an_empty_run_is_empty() -> None:
    daily = build_daily_series(build_equity_series(bars=(), trades=(), initial_capital=INITIAL))

    assert daily.is_empty
    assert daily.day_count == 0
