"""Deterministic validation scenarios for the execution engine."""

from __future__ import annotations

from dataclasses import dataclass

from app.engine.bars import Bar, BarIterator
from app.engine.runner import ExecutionConfig


@dataclass(frozen=True)
class ScenarioExpectation:
    trade_count: int
    final_cash: float
    net_profit: float
    gross_pnl: float | None = None
    position_closed: bool = True


@dataclass(frozen=True)
class ValidationScenario:
    name: str
    description: str
    strategy_source: str
    bars: tuple[Bar, ...]
    config: ExecutionConfig
    expected: ScenarioExpectation

    def iterator(self) -> BarIterator:
        return BarIterator(self.bars)


def _bar(
    index: int,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: float = 100.0,
    step_ms: int = 60_000,
) -> Bar:
    return Bar(
        ts=1_704_067_500_000 + index * step_ms,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


BUY_ONCE = """
class Strategy:
    def on_bar(self, bar):
        if self.ctx.position is None:
            self.ctx.buy(10)
"""

BUY_CLOSE_ON_GAIN = """
class Strategy:
    def on_bar(self, bar):
        if self.ctx.position is None:
            self.ctx.buy(10)
        elif bar.close > self.ctx.position.entry_price:
            self.ctx.close()
"""

SHORT_ONCE = """
class Strategy:
    def on_start(self):
        self.ctx.sell(10)
"""

SHORT_CLOSE_ON_DROP = """
class Strategy:
    def on_start(self):
        self.ctx.sell(10)

    def on_bar(self, bar):
        if self.ctx.position and bar.close < self.ctx.position.entry_price:
            self.ctx.close()
"""

NO_OP = """
class Strategy:
    pass
"""

MULTI_TRADE = """
class Strategy:
    def on_bar(self, bar):
        if self.ctx.position is None:
            self.ctx.buy(5)
        else:
            self.ctx.close()
"""

VALIDATION_SCENARIOS: tuple[ValidationScenario, ...] = (
    ValidationScenario(
        name="simple_long_win",
        description="Single long round-trip with profit and no costs",
        strategy_source=BUY_CLOSE_ON_GAIN,
        bars=(
            _bar(0, open_=100, high=101, low=99, close=100),
            _bar(1, open_=100, high=101, low=99, close=100),
            _bar(2, open_=100, high=105, low=99, close=104),
            _bar(3, open_=105, high=106, low=104, close=105),
        ),
        config=ExecutionConfig(initial_capital=10_000, commission=0, slippage=0),
        expected=ScenarioExpectation(
            trade_count=1,
            final_cash=10_050.0,
            net_profit=50.0,
            gross_pnl=50.0,
        ),
    ),
    ValidationScenario(
        name="simple_long_loss",
        description="Single long round-trip with loss and no costs",
        strategy_source="""
class Strategy:
    def on_bar(self, bar):
        if self.ctx.position is None:
            self.ctx.buy(10)
        elif bar.close <= 90:
            self.ctx.close()
""",
        bars=(
            _bar(0, open_=100, high=101, low=99, close=100),
            _bar(1, open_=100, high=101, low=99, close=100),
            _bar(2, open_=90, high=91, low=89, close=90),
            _bar(3, open_=90, high=91, low=89, close=90),
        ),
        config=ExecutionConfig(initial_capital=10_000, commission=0, slippage=0),
        expected=ScenarioExpectation(
            trade_count=1,
            final_cash=9_900.0,
            net_profit=-100.0,
            gross_pnl=-100.0,
        ),
    ),
    ValidationScenario(
        name="simple_short_win",
        description="Short opened on start and covered lower",
        strategy_source=SHORT_CLOSE_ON_DROP,
        bars=(
            _bar(0, open_=100, high=101, low=99, close=100),
            _bar(1, open_=100, high=101, low=99, close=100),
            _bar(2, open_=95, high=96, low=94, close=95),
            _bar(3, open_=95, high=96, low=94, close=95),
        ),
        config=ExecutionConfig(initial_capital=10_000, commission=0, slippage=0),
        expected=ScenarioExpectation(
            trade_count=1,
            final_cash=10_050.0,
            net_profit=50.0,
            gross_pnl=50.0,
        ),
    ),
    ValidationScenario(
        name="breakeven_trade",
        description="Round trip with zero gross P&L",
        strategy_source=BUY_CLOSE_ON_GAIN,
        bars=(
            _bar(0, open_=100, high=101, low=99, close=100),
            _bar(1, open_=100, high=101, low=99, close=100),
            _bar(2, open_=100, high=101, low=99, close=101),
            _bar(3, open_=100, high=101, low=99, close=100),
        ),
        config=ExecutionConfig(initial_capital=10_000, commission=0, slippage=0),
        expected=ScenarioExpectation(
            trade_count=1,
            final_cash=10_000.0,
            net_profit=0.0,
            gross_pnl=0.0,
        ),
    ),
    ValidationScenario(
        name="commission_only",
        description="Commission applied without slippage",
        strategy_source=BUY_CLOSE_ON_GAIN,
        bars=(
            _bar(0, open_=100, high=101, low=99, close=100),
            _bar(1, open_=100, high=101, low=99, close=100),
            _bar(2, open_=100, high=105, low=99, close=104),
            _bar(3, open_=105, high=106, low=104, close=105),
        ),
        config=ExecutionConfig(initial_capital=10_000, commission=0.001, slippage=0),
        expected=ScenarioExpectation(
            trade_count=1,
            final_cash=10_047.95,
            net_profit=47.95,
            gross_pnl=50.0,
        ),
    ),
    ValidationScenario(
        name="slippage_only",
        description="Slippage applied without commission",
        strategy_source=BUY_CLOSE_ON_GAIN,
        bars=(
            _bar(0, open_=100, high=101, low=99, close=100),
            _bar(1, open_=100, high=101, low=99, close=100),
            _bar(2, open_=100, high=105, low=99, close=104),
            _bar(3, open_=105, high=106, low=104, close=105),
        ),
        config=ExecutionConfig(initial_capital=10_000, commission=0, slippage=0.01),
        expected=ScenarioExpectation(
            trade_count=1,
            final_cash=10_029.5,
            net_profit=29.5,
            gross_pnl=29.5,
        ),
    ),
    ValidationScenario(
        name="commission_and_slippage",
        description="Both commission and slippage applied",
        strategy_source=BUY_CLOSE_ON_GAIN,
        bars=(
            _bar(0, open_=100, high=101, low=99, close=100),
            _bar(1, open_=100, high=101, low=99, close=100),
            _bar(2, open_=100, high=105, low=99, close=104),
            _bar(3, open_=105, high=106, low=104, close=105),
        ),
        config=ExecutionConfig(initial_capital=10_000, commission=0.001, slippage=0.01),
        expected=ScenarioExpectation(
            trade_count=1,
            final_cash=10_027.4505,
            net_profit=27.4505,
            gross_pnl=29.5,
        ),
    ),
    ValidationScenario(
        name="gap_up",
        description="Entry fills on gap-up open",
        strategy_source=BUY_ONCE,
        bars=(
            _bar(0, open_=100, high=101, low=99, close=100),
            _bar(1, open_=110, high=112, low=109, close=111),
        ),
        config=ExecutionConfig(initial_capital=10_000, commission=0, slippage=0),
        expected=ScenarioExpectation(
            trade_count=0,
            final_cash=8_900.0,
            net_profit=-1_100.0,
            position_closed=False,
        ),
    ),
    ValidationScenario(
        name="gap_down",
        description="Short entry fills on gap-down open",
        strategy_source=SHORT_ONCE,
        bars=(
            _bar(0, open_=100, high=101, low=99, close=100),
            _bar(1, open_=90, high=91, low=89, close=90),
        ),
        config=ExecutionConfig(initial_capital=10_000, commission=0, slippage=0),
        expected=ScenarioExpectation(
            trade_count=0,
            final_cash=11_000.0,
            net_profit=1_000.0,
            position_closed=False,
        ),
    ),
    ValidationScenario(
        name="multiple_consecutive_trades",
        description="Alternating open/close across bars",
        strategy_source=MULTI_TRADE,
        bars=tuple(
            _bar(i, open_=100 + i, high=101 + i, low=99 + i, close=100 + i) for i in range(5)
        ),
        config=ExecutionConfig(initial_capital=10_000, commission=0, slippage=0),
        expected=ScenarioExpectation(
            trade_count=2,
            final_cash=10_010.0,
            net_profit=10.0,
        ),
    ),
    ValidationScenario(
        name="no_trades",
        description="Strategy never submits orders",
        strategy_source=NO_OP,
        bars=(
            _bar(0, open_=100, high=101, low=99, close=100),
            _bar(1, open_=101, high=102, low=100, close=101),
        ),
        config=ExecutionConfig(initial_capital=10_000, commission=0, slippage=0),
        expected=ScenarioExpectation(
            trade_count=0,
            final_cash=10_000.0,
            net_profit=0.0,
        ),
    ),
    ValidationScenario(
        name="large_position",
        description="Large quantity long with no costs",
        strategy_source="""
class Strategy:
    def on_bar(self, bar):
        if self.ctx.position is None:
            self.ctx.buy(1000)
        elif bar.close >= 11:
            self.ctx.close()
""",
        bars=(
            _bar(0, open_=10, high=11, low=9, close=10),
            _bar(1, open_=10, high=11, low=9, close=10),
            _bar(2, open_=11, high=12, low=10, close=11),
            _bar(3, open_=11, high=12, low=10, close=11),
        ),
        config=ExecutionConfig(initial_capital=1_000_000, commission=0, slippage=0),
        expected=ScenarioExpectation(
            trade_count=1,
            final_cash=1_001_000.0,
            net_profit=1_000.0,
            gross_pnl=1_000.0,
        ),
    ),
    ValidationScenario(
        name="fractional_quantity",
        description="Fractional share quantity is supported",
        strategy_source="""
class Strategy:
    def on_bar(self, bar):
        if self.ctx.position is None:
            self.ctx.buy(1.5)
        elif bar.close >= 110:
            self.ctx.close()
""",
        bars=(
            _bar(0, open_=100, high=101, low=99, close=100),
            _bar(1, open_=100, high=101, low=99, close=100),
            _bar(2, open_=110, high=111, low=109, close=110),
            _bar(3, open_=110, high=111, low=109, close=110),
        ),
        config=ExecutionConfig(initial_capital=10_000, commission=0, slippage=0),
        expected=ScenarioExpectation(
            trade_count=1,
            final_cash=10_015.0,
            net_profit=15.0,
            gross_pnl=15.0,
        ),
    ),
)
