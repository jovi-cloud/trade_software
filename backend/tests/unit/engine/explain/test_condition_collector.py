"""Condition collector unit tests."""

from __future__ import annotations

from app.engine.explain.condition_collector import ConditionCollector


def test_condition_collector_builds_snapshot() -> None:
    collector = ConditionCollector()
    collector.trace_condition(
        "RSI > 60",
        actual="55",
        expected="True",
        passed=False,
    )
    collector.trace_indicator("RSI", 55.0)
    snapshot = collector.snapshot(bar_index=3)
    assert snapshot.bar_index == 3
    assert len(snapshot.conditions) == 1
    assert snapshot.indicators["RSI"] == 55.0


def test_clear_resets_collector() -> None:
    collector = ConditionCollector()
    collector.trace_condition("A", actual="1", expected="1", passed=True)
    collector.clear()
    snapshot = collector.snapshot(bar_index=0)
    assert snapshot.conditions == ()
