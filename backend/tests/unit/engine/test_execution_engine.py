"""ExecutionEngine unit tests."""

from __future__ import annotations

import pytest

from app.engine.bars import Bar, BarIterator
from app.engine.runner import ExecutionConfig, ExecutionEngine

COUNTING_STRATEGY = """
class Strategy:
    def on_start(self):
        self.count = 0

    def on_bar(self, bar):
        self.count += 1
        self.ctx.log(self.count, bar.close)

    def on_stop(self):
        self.ctx.log("stopped at", self.count)
"""

BROKEN_STRATEGY = """
class Strategy:
    def on_bar(self, bar):
        raise ValueError("boom")
"""

NO_STRATEGY_CLASS = "x = 1"


def _bars(count: int = 3) -> BarIterator:
    return BarIterator(
        [
            Bar(
                ts=1_704_067_500_000 + i * 60_000,
                open=100,
                high=101,
                low=99,
                close=100 + i,
                volume=10,
            )
            for i in range(count)
        ]
    )


def test_run_replays_bars_and_collects_logs() -> None:
    result = ExecutionEngine().run(strategy_source=COUNTING_STRATEGY, bars=_bars(3))

    assert result.completed is True
    assert result.bars_processed == 3
    assert result.errors == ()
    assert result.strategy_logs == ("1 100", "2 101", "3 102", "stopped at 3")


def test_run_reports_compile_error_without_raising() -> None:
    result = ExecutionEngine().run(strategy_source="def broken(:\n    pass", bars=_bars())

    assert result.completed is False
    assert result.bars_processed == 0
    assert len(result.errors) == 1
    assert "Syntax error" in result.errors[0]


def test_run_reports_missing_strategy_class() -> None:
    result = ExecutionEngine().run(strategy_source=NO_STRATEGY_CLASS, bars=_bars())

    assert result.completed is False
    assert "No class named 'Strategy'" in result.errors[0]


def test_run_halts_on_first_on_bar_failure() -> None:
    result = ExecutionEngine().run(strategy_source=BROKEN_STRATEGY, bars=_bars(5))

    assert result.completed is False
    assert result.bars_processed == 0
    assert len(result.errors) == 1
    assert "on_bar raised ValueError" in result.errors[0]


def test_run_warns_on_empty_dataset() -> None:
    result = ExecutionEngine().run(strategy_source=COUNTING_STRATEGY, bars=BarIterator([]))

    assert result.completed is True
    assert result.bars_processed == 0
    assert any("no bars" in warning.lower() for warning in result.warnings)


def test_config_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        ExecutionConfig(initial_capital=0)

    with pytest.raises(ValueError):
        ExecutionConfig(commission=-1)
