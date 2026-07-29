"""Execution simulator and trading rules."""

from __future__ import annotations

from app.domain.enums import OrderStatus, OrderType, PositionSide
from app.engine.bars import Bar, BarIterator
from app.engine.runner import ExecutionConfig, ExecutionEngine

BUY_HOLD_STRATEGY = """
class Strategy:
    def on_bar(self, bar):
        if self.ctx.position is None:
            self.ctx.buy(10)
"""


BUY_SELL_STRATEGY = """
class Strategy:
    def on_bar(self, bar):
        if self.ctx.position is None:
            self.ctx.buy(10)
        elif bar.close > self.ctx.position.entry_price + 1:
            self.ctx.close()
"""


SHORT_STRATEGY = """
class Strategy:
    def on_start(self):
        self.ctx.sell(5)
"""


DOUBLE_BUY_STRATEGY = """
class Strategy:
    def on_bar(self, bar):
        self.ctx.buy(1)
        self.ctx.buy(1)
"""


def _bars(prices: list[float]) -> BarIterator:
    return BarIterator(
        [
            Bar(
                ts=1_704_067_500_000 + i * 60_000,
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=100,
            )
            for i, price in enumerate(prices)
        ]
    )


def test_buy_fills_on_next_bar_open() -> None:
    result = ExecutionEngine(ExecutionConfig(initial_capital=10_000)).run(
        strategy_source=BUY_HOLD_STRATEGY,
        bars=_bars([100, 101, 102]),
    )

    assert result.completed is True
    assert result.trade_count == 0
    assert result.position_closed is False
    filled = [order for order in result.orders if order.status is OrderStatus.FILLED]
    assert len(filled) == 1
    assert filled[0].order_type is OrderType.BUY_MARKET
    assert filled[0].filled_bar_index == 1


def test_close_records_trade() -> None:
    result = ExecutionEngine(ExecutionConfig(initial_capital=10_000, commission=0, slippage=0)).run(
        strategy_source=BUY_SELL_STRATEGY,
        bars=_bars([100, 100, 103, 103]),
    )

    assert result.trade_count == 1
    trade = result.trades[0]
    assert trade.side is PositionSide.LONG
    assert trade.quantity == 10
    assert trade.entry_price == 100
    assert trade.exit_price == 103
    assert trade.gross_pnl == 30
    assert result.position_closed is True


def test_sell_opens_short_from_on_start() -> None:
    result = ExecutionEngine(ExecutionConfig(initial_capital=10_000)).run(
        strategy_source=SHORT_STRATEGY,
        bars=_bars([100, 101]),
    )

    filled = [order for order in result.orders if order.status is OrderStatus.FILLED]
    assert len(filled) == 1
    assert filled[0].order_type is OrderType.SELL_MARKET
    assert filled[0].filled_bar_index == 0
    assert result.position_closed is False


def test_second_buy_while_position_open_warns() -> None:
    result = ExecutionEngine().run(
        strategy_source=DOUBLE_BUY_STRATEGY,
        bars=_bars([100, 101]),
    )

    assert any("already open" in warning for warning in result.warnings)
    assert len(result.orders) == 2
    assert sum(1 for order in result.orders if order.status is OrderStatus.FILLED) == 1


def test_slippage_trade_reconciles_with_final_cash() -> None:
    result = ExecutionEngine(
        ExecutionConfig(initial_capital=10_000, commission=0, slippage=0.01)
    ).run(
        strategy_source=BUY_SELL_STRATEGY,
        bars=_bars([100, 100, 103, 103]),
    )

    assert result.trade_count == 1
    trade = result.trades[0]
    assert result.final_cash == 10_000 + trade.net_pnl


def test_commission_and_slippage_reduce_cash() -> None:
    no_cost = ExecutionEngine(ExecutionConfig(initial_capital=10_000)).run(
        strategy_source=BUY_HOLD_STRATEGY,
        bars=_bars([100, 101]),
    )
    with_cost = ExecutionEngine(
        ExecutionConfig(initial_capital=10_000, commission=0.01, slippage=0.01)
    ).run(strategy_source=BUY_HOLD_STRATEGY, bars=_bars([100, 101]))

    assert with_cost.final_cash < no_cost.final_cash


def test_insufficient_cash_rejects_buy() -> None:
    strategy = """
class Strategy:
    def on_bar(self, bar):
        self.ctx.buy(1000)
"""
    result = ExecutionEngine(ExecutionConfig(initial_capital=100)).run(
        strategy_source=strategy,
        bars=_bars([100, 101]),
    )

    assert any("insufficient cash" in warning.lower() for warning in result.warnings)
    assert result.position_closed is True


def test_unfilled_orders_warn_at_dataset_end() -> None:
    strategy = """
class Strategy:
    def on_bar(self, bar):
        self.ctx.buy(1)
"""
    result = ExecutionEngine().run(strategy_source=strategy, bars=_bars([100]))

    assert any("not filled" in warning.lower() for warning in result.warnings)
