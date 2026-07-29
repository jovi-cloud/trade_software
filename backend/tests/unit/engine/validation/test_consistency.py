"""Deterministic repeat-execution checks."""

from __future__ import annotations

from app.engine.runner import ExecutionEngine
from app.engine.validation.hashing import hash_execution_result
from app.engine.validation.scenarios import VALIDATION_SCENARIOS


def test_repeated_execution_produces_identical_hashes() -> None:
    scenario = VALIDATION_SCENARIOS[0]
    engine = ExecutionEngine(scenario.config)
    hashes: set[str] = set()
    for _ in range(10):
        result = engine.run(strategy_source=scenario.strategy_source, bars=scenario.iterator())
        hashes.add(hash_execution_result(result, initial_capital=scenario.config.initial_capital))
    assert len(hashes) == 1
