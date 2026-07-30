"""Built-in reference strategies run through the real engine."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from app.domain.explain import ExplainLevel
from app.engine.bars import BarIterator
from app.engine.results.result import ExecutionResult
from app.engine.runner import ExecutionConfig, ExecutionEngine
from app.engine.strategy.provider import LibraryStrategyProvider
from app.engine.strategy.registry import StrategyRegistry
from tests.unit.engine.strategy.conftest import bars_from_closes


def _run_library_strategy(
    strategy_id: str, params: Mapping[str, object] | None = None
) -> ExecutionResult:
    registry = StrategyRegistry()
    registry.discover()
    definition = registry.get(strategy_id)
    bars = bars_from_closes([100.0 + index * 0.5 for index in range(120)])
    return ExecutionEngine(
        ExecutionConfig(initial_capital=100_000.0, explain_level=ExplainLevel.FULL)
    ).run(
        bars=BarIterator(bars),
        strategy=LibraryStrategyProvider(definition.strategy_class, params),
    )


def _has_condition_traces(result: ExecutionResult) -> bool:
    for event in result.explain_events:
        conditions = event.metadata.get("conditions")
        if isinstance(conditions, list) and conditions:
            return True
    return False


@pytest.mark.parametrize(
    "strategy_id",
    [
        "opening_range_breakout",
        "ema_crossover",
        "sma_crossover",
        "vwap_reversion",
        "rsi_mean_reversion",
        "bollinger_bands",
        "macd",
        "donchian_breakout",
        "supertrend",
        "ma_pullback",
    ],
)
def test_reference_strategy_runs_and_traces_conditions(strategy_id: str) -> None:
    result = _run_library_strategy(strategy_id)
    assert result.completed
    assert _has_condition_traces(result)


def test_registry_loads_defaults_for_every_reference_strategy() -> None:
    registry = StrategyRegistry()
    registry.discover()
    for strategy_id in registry.ids():
        instance = registry.load(strategy_id)
        assert instance.metadata.id == strategy_id
