"""Integration tests for explain events on execution."""

from __future__ import annotations

from app.domain.explain import ExplainEventType, ExplainLevel
from app.engine.bars import Bar, BarIterator
from app.engine.runner import ExecutionConfig, ExecutionEngine

BUY_SELL = """
class Strategy:
    def on_bar(self, bar):
        if self.ctx.position is None:
            self.ctx.buy(10)
        elif bar.close > self.ctx.position.entry_price:
            self.ctx.close()
"""


def _bars(closes: list[float]) -> BarIterator:
    return BarIterator(
        [
            Bar(
                ts=1_704_067_500_000 + index * 60_000,
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=100,
            )
            for index, price in enumerate(closes)
        ]
    )


def test_execution_engine_emits_structured_explain_events() -> None:
    result = ExecutionEngine(
        ExecutionConfig(explain_level=ExplainLevel.TRADES_ONLY)
    ).run(strategy_source=BUY_SELL, bars=_bars([100, 100, 103, 103]))

    assert result.explain_level is ExplainLevel.TRADES_ONLY
    assert len(result.explain_events) > 0
    types = {event.event_type for event in result.explain_events}
    assert ExplainEventType.RUN_STARTED in types
    assert ExplainEventType.ORDER_SUBMITTED in types
    assert ExplainEventType.ORDER_FILLED in types
    assert ExplainEventType.POSITION_OPENED in types
    assert ExplainEventType.POSITION_CLOSED in types
    assert ExplainEventType.RUN_COMPLETED in types


def test_explain_none_produces_no_events() -> None:
    result = ExecutionEngine(
        ExecutionConfig(explain_level=ExplainLevel.NONE)
    ).run(strategy_source=BUY_SELL, bars=_bars([100, 100, 103, 103]))

    assert result.explain_events == ()


def test_explain_does_not_change_trade_outcomes() -> None:
    bars = _bars([100, 100, 103, 103])
    with_explain = ExecutionEngine(
        ExecutionConfig(explain_level=ExplainLevel.FULL)
    ).run(strategy_source=BUY_SELL, bars=bars)
    without = ExecutionEngine(
        ExecutionConfig(explain_level=ExplainLevel.NONE)
    ).run(strategy_source=BUY_SELL, bars=bars)

    assert with_explain.trade_count == without.trade_count
    assert with_explain.final_cash == without.final_cash
    assert with_explain.trades == without.trades
