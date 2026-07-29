"""StrategyLoader sandbox and compile behaviour."""

from __future__ import annotations

import pytest

from app.engine.bars import Bar
from app.engine.context import ExecutionContext, LogCollector
from app.engine.errors import StrategyCompileError
from app.engine.execution.order_book import OrderBook
from app.engine.execution.order_service import OrderService
from app.engine.execution.portfolio import PortfolioManager
from app.engine.strategy.loader import StrategyLoader

VALID_STRATEGY = """
class Strategy:
    def on_bar(self, bar):
        self.ctx.log(bar.close)
        print("via print")
"""


def test_load_compiles_and_instantiates_strategy() -> None:
    logs = LogCollector()
    strategy = StrategyLoader(logs).load(VALID_STRATEGY)

    assert strategy.defines_on_bar is True
    assert strategy.defined_hooks == ("on_bar",)


def test_load_rejects_empty_source() -> None:
    with pytest.raises(StrategyCompileError, match="empty"):
        StrategyLoader(LogCollector()).load("   ")


def test_load_rejects_missing_strategy_class() -> None:
    with pytest.raises(StrategyCompileError, match="No class named 'Strategy'"):
        StrategyLoader(LogCollector()).load("answer = 42")


def test_restricted_namespace_blocks_open_at_module_level() -> None:
    with pytest.raises(StrategyCompileError, match="failed to execute"):
        StrategyLoader(LogCollector()).load("open('/etc/passwd')\nclass Strategy:\n    pass\n")


def test_print_is_captured_into_logs() -> None:
    logs = LogCollector()
    strategy = StrategyLoader(logs).load(VALID_STRATEGY)
    portfolio = PortfolioManager(10_000)
    warnings: list[str] = []
    order_book = OrderBook()
    order_service = OrderService(order_book, portfolio, warnings)
    context = ExecutionContext(
        initial_capital=10_000,
        portfolio=portfolio,
        order_service=order_service,
        logs=logs,
    )
    strategy.bind_context(context)
    strategy.call_on_bar(Bar(ts=0, open=1, high=2, low=0.5, close=1.5, volume=10))

    assert "via print" in logs.entries
