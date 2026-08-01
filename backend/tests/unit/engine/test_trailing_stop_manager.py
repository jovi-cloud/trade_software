"""Tests for TrailingStopManager."""

from __future__ import annotations

import pytest

from app.domain.enums import PositionSide
from app.engine.bars import Bar
from app.engine.execution.trailing_stop import (
    TrailingMethod,
    TrailingStopConfig,
    TrailingStopManager,
)
from app.engine.strategy.risk import RiskRules, TradeRiskState, evaluate_risk_exit
from tests.unit.engine.strategy.test_risk import bars_from_ohlc


def _bar(high: float, low: float, close: float = 100.0) -> Bar:
    return bars_from_ohlc([(close, high, low, close)])[0]


def test_long_percent_trailing_matches_spec_example() -> None:
    config = TrailingStopConfig(method=TrailingMethod.PERCENT, percent=2.0)
    manager = TrailingStopManager.open(
        config=config,
        side=PositionSide.LONG,
        entry_price=100.0,
        atr_at_entry=None,
    )
    assert manager.current_trailing_stop == pytest.approx(98.0)

    for high in (100.0, 101.0, 103.0, 105.0):
        manager.on_bar(_bar(high=high, low=high - 0.5), None)
    assert manager.current_trailing_stop == pytest.approx(102.90)

    assert manager.is_breached(_bar(high=103.0, low=102.90))


def test_short_percent_trailing_matches_spec_example() -> None:
    config = TrailingStopConfig(method=TrailingMethod.PERCENT, percent=2.0)
    manager = TrailingStopManager.open(
        config=config,
        side=PositionSide.SHORT,
        entry_price=100.0,
        atr_at_entry=None,
    )
    assert manager.current_trailing_stop == pytest.approx(102.0)

    for low in (100.0, 98.0, 96.0, 94.0):
        manager.on_bar(_bar(high=low + 0.5, low=low), None)
    assert manager.current_trailing_stop == pytest.approx(95.88)


def test_points_method_long() -> None:
    config = TrailingStopConfig(method=TrailingMethod.POINTS, points=1.5)
    manager = TrailingStopManager.open(
        config=config,
        side=PositionSide.LONG,
        entry_price=50.0,
        atr_at_entry=None,
    )
    manager.on_bar(_bar(high=55.0, low=54.0), None)
    assert manager.current_trailing_stop == pytest.approx(53.5)


def test_atr_method_long() -> None:
    config = TrailingStopConfig(method=TrailingMethod.ATR, atr_multiplier=2.0)
    manager = TrailingStopManager.open(
        config=config,
        side=PositionSide.LONG,
        entry_price=100.0,
        atr_at_entry=2.5,
    )
    manager.on_bar(_bar(high=110.0, low=108.0), atr=3.0)
    assert manager.current_trailing_stop == pytest.approx(104.0)


def _percent_trailing_rules() -> RiskRules:
    return RiskRules(
        trailing_config=TrailingStopConfig(method=TrailingMethod.PERCENT, percent=2.0),
    )


def test_gap_down_triggers_exit() -> None:
    rules = _percent_trailing_rules()
    state = TradeRiskState.open(
        side=PositionSide.LONG,
        entry_price=100.0,
        entry_bar_index=0,
        atr=None,
        rules=rules,
    )
    state.observe(_bar(high=120.0, low=118.0))
    exit_ = evaluate_risk_exit(
        state,
        bar=_bar(high=105.0, low=100.0),
        bars_held=2,
        rules=rules,
        atr=None,
        clock=None,
    )
    assert exit_ is not None
    assert exit_.code == "trailing_stop"


def test_multiple_trades_reset_state() -> None:
    rules = _percent_trailing_rules()
    first = TradeRiskState.open(
        side=PositionSide.LONG,
        entry_price=100.0,
        entry_bar_index=0,
        atr=None,
        rules=rules,
    )
    first.observe(_bar(high=110.0, low=109.0))
    second = TradeRiskState.open(
        side=PositionSide.LONG,
        entry_price=200.0,
        entry_bar_index=5,
        atr=None,
        rules=rules,
    )
    assert second.highest_price_since_entry == 200.0
    assert second.trailing is not None
    assert second.trailing.current_trailing_stop == pytest.approx(196.0)


def test_engine_records_trailing_stop_chart_points() -> None:
    from app.domain.explain import ExplainLevel
    from app.engine.bars import BarIterator
    from app.engine.runner import ExecutionConfig, ExecutionEngine
    from app.engine.strategy.provider import LibraryStrategyProvider
    from app.engine.strategy.registry import StrategyRegistry
    from tests.unit.engine.strategy.conftest import bars_from_ohlc

    registry = StrategyRegistry()
    registry.discover()
    definition = registry.get("ema_crossover")
    bars = bars_from_ohlc(
        [
            (100.0, 101.0, 99.0, 100.5),
            (100.5, 102.0, 100.0, 101.5),
            (101.5, 105.0, 101.0, 104.0),
            (104.0, 106.0, 103.0, 105.0),
            (105.0, 105.5, 102.0, 102.5),
            (102.5, 103.0, 101.0, 101.5),
        ]
    )
    result = ExecutionEngine(
        ExecutionConfig(initial_capital=100_000.0, explain_level=ExplainLevel.NONE)
    ).run(
        bars=BarIterator(bars),
        strategy=LibraryStrategyProvider(
            definition.strategy_class,
            {
                "enable_trailing_stop": True,
                "trailing_method": "percent",
                "trailing_stop_percent": 2.0,
                "fast_period": 2,
                "slow_period": 4,
                "trend_filter_period": 0,
                "direction": "both",
            },
        ),
    )
    assert result.completed
    if result.trade_count > 0:
        assert len(result.trailing_stop_points) > 0
