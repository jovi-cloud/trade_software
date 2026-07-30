"""Deterministic fixtures for the analytics layer.

Every helper produces daily bars starting 2025-01-01 UTC so that a bar index is
a day index. That makes an expected value hand-checkable: 10 bars is 10 trading
days, and monthly grouping is obvious from the index.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from app.analytics.inputs import MS_PER_DAY, AnalyticsConfig, AnalyticsInput, BarRecord, TradeRecord
from app.domain.enums import PositionSide

#: 2025-01-01T00:00:00Z
DAY_ZERO = 1_735_689_600_000
INITIAL = 10_000.0


def ts_at(day: int) -> int:
    """Epoch ms for bar/day ``day``."""
    return DAY_ZERO + day * MS_PER_DAY


def bars(closes: Sequence[float], *, spread: float = 1.0) -> tuple[BarRecord, ...]:
    """One daily bar per close, with a symmetric high/low around it."""
    return tuple(
        BarRecord(
            ts=ts_at(index),
            open=close,
            high=close + spread,
            low=close - spread,
            close=close,
            volume=1.0,
        )
        for index, close in enumerate(closes)
    )


def trade(
    seq: int,
    *,
    entry_day: int,
    exit_day: int,
    entry_price: float,
    exit_price: float,
    quantity: float = 1.0,
    side: PositionSide = PositionSide.LONG,
    commission: float = 0.0,
    slippage_cost: float = 0.0,
) -> TradeRecord:
    """A round trip whose P&L follows from its prices - nothing hand-tuned."""
    direction = 1.0 if side is PositionSide.LONG else -1.0
    gross = direction * (exit_price - entry_price) * quantity
    return TradeRecord(
        seq=seq,
        side=side,
        quantity=quantity,
        entry_ts=ts_at(entry_day),
        entry_price=entry_price,
        exit_ts=ts_at(exit_day),
        exit_price=exit_price,
        gross_pnl=gross,
        commission=commission,
        slippage_cost=slippage_cost,
        net_pnl=gross - commission - slippage_cost,
        bars_held=exit_day - entry_day,
    )


def pnl_trade(seq: int, net_pnl: float, *, entry_day: int, exit_day: int) -> TradeRecord:
    """A trade specified by its P&L, for tests about counts and streaks."""
    return trade(
        seq,
        entry_day=entry_day,
        exit_day=exit_day,
        entry_price=100.0,
        exit_price=100.0 + net_pnl,
    )


def make_input(
    *,
    trades: tuple[TradeRecord, ...] = (),
    closes: Sequence[float] = (),
    initial_capital: float = INITIAL,
    config: AnalyticsConfig | None = None,
) -> AnalyticsInput:
    return AnalyticsInput(
        trades=trades,
        bars=bars(closes),
        initial_capital=initial_capital,
        config=config or AnalyticsConfig(),
    )


@pytest.fixture
def reference_input() -> AnalyticsInput:
    """The reference dataset used for regression protection.

    Two winning trades on a rising market with two intervening pullbacks. Small
    enough that every metric can be verified by hand, which is why the golden
    test in ``test_reference.py`` pins its numbers.
    """
    return make_input(
        trades=(
            trade(1, entry_day=0, exit_day=3, entry_price=100.0, exit_price=120.0),
            trade(2, entry_day=5, exit_day=8, entry_price=130.0, exit_price=135.0),
        ),
        closes=(100, 110, 105, 120, 115, 130, 125, 140, 135, 150),
    )
