"""Deterministic MetricsEngine unit tests."""

from __future__ import annotations

from app.domain.enums import PositionSide
from app.engine.execution.trade import Trade
from app.engine.results.metrics import MetricsEngine

INITIAL = 10_000.0


def _trade(
    seq: int,
    *,
    net_pnl: float,
    commission: float = 0.0,
    slippage_cost: float = 0.0,
    bars_held: int = 2,
) -> Trade:
    gross = net_pnl + commission + slippage_cost
    return Trade(
        seq=seq,
        side=PositionSide.LONG,
        quantity=1.0,
        entry_ts=1_000 + seq,
        entry_price=100.0,
        exit_ts=2_000 + seq,
        exit_price=100.0 + gross,
        gross_pnl=gross,
        commission=commission,
        slippage_cost=slippage_cost,
        net_pnl=net_pnl,
        bars_held=bars_held,
    )


def test_no_trades_returns_zeroed_metrics() -> None:
    metrics, equity = MetricsEngine().compute(
        trades=[], initial_capital=INITIAL, final_cash=INITIAL
    )

    assert metrics.total_trades == 0
    assert metrics.net_profit == 0.0
    assert metrics.return_pct == 0.0
    assert metrics.win_rate_pct == 0.0
    assert equity == ()


def test_all_winning_trades() -> None:
    trades = (_trade(1, net_pnl=100), _trade(2, net_pnl=50))
    metrics, equity = MetricsEngine().compute(
        trades=trades, initial_capital=INITIAL, final_cash=INITIAL + 150
    )

    assert metrics.total_trades == 2
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 0
    assert metrics.gross_profit == 150.0
    assert metrics.gross_loss == 0.0
    assert metrics.net_profit == 150.0
    assert metrics.win_rate_pct == 100.0
    assert metrics.largest_win == 100.0
    assert metrics.average_win == 75.0
    assert metrics.return_pct == 1.5
    assert len(equity) == 2
    assert equity[0].equity == INITIAL + 100
    assert equity[1].equity == INITIAL + 150


def test_all_losing_trades() -> None:
    trades = (_trade(1, net_pnl=-40), _trade(2, net_pnl=-10))
    metrics, _ = MetricsEngine().compute(
        trades=trades, initial_capital=INITIAL, final_cash=INITIAL - 50
    )

    assert metrics.winning_trades == 0
    assert metrics.losing_trades == 2
    assert metrics.gross_loss == 50.0
    assert metrics.largest_loss == 40.0
    assert metrics.average_loss == 25.0
    assert metrics.net_profit == -50.0


def test_mixed_trades() -> None:
    trades = (_trade(1, net_pnl=80), _trade(2, net_pnl=-30), _trade(3, net_pnl=20))
    metrics, _ = MetricsEngine().compute(
        trades=trades, initial_capital=INITIAL, final_cash=INITIAL + 70
    )

    assert metrics.total_trades == 3
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 1
    assert metrics.gross_profit == 100.0
    assert metrics.gross_loss == 30.0
    assert metrics.profit_factor == round(100 / 30, 6)
    assert metrics.expectancy == round(70 / 3, 6)
    assert metrics.win_rate_pct == round(200 / 3, 6)


def test_commission_only_reduces_net_profit() -> None:
    trades = (_trade(1, net_pnl=-5, commission=5.0),)
    metrics, _ = MetricsEngine().compute(
        trades=trades, initial_capital=INITIAL, final_cash=INITIAL - 5
    )

    assert metrics.commission_paid == 5.0
    assert metrics.slippage_cost == 0.0
    assert metrics.net_profit == -5.0


def test_slippage_only_reduces_net_profit() -> None:
    trades = (_trade(1, net_pnl=-3, slippage_cost=3.0),)
    metrics, _ = MetricsEngine().compute(
        trades=trades, initial_capital=INITIAL, final_cash=INITIAL - 3
    )

    assert metrics.slippage_cost == 3.0
    assert metrics.commission_paid == 0.0
    assert metrics.net_profit == -3.0


def test_average_holding_bars() -> None:
    trades = (_trade(1, net_pnl=1, bars_held=2), _trade(2, net_pnl=1, bars_held=4))
    metrics, _ = MetricsEngine().compute(
        trades=trades, initial_capital=INITIAL, final_cash=INITIAL + 2
    )

    assert metrics.average_holding_bars == 3.0
