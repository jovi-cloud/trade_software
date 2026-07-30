"""Per-bar condition and indicator snapshots from strategy observation."""

from __future__ import annotations

from app.domain.conditions import ConditionSnapshot, ConditionTrace


class ConditionCollector:
    """Buffers strategy-published traces for one bar, then flushes to explain."""

    def __init__(self) -> None:
        self._conditions: list[ConditionTrace] = []
        self._indicators: dict[str, float | str] = {}

    def clear(self) -> None:
        self._conditions = []
        self._indicators = {}

    def trace_condition(
        self,
        name: str,
        *,
        actual: str,
        expected: str,
        passed: bool,
    ) -> None:
        self._conditions.append(
            ConditionTrace(
                name=name,
                actual_value=actual,
                expected_value=expected,
                passed=passed,
            )
        )

    def trace_indicator(self, name: str, value: float | str) -> None:
        self._indicators[name] = value

    def add_inferred_condition(
        self,
        name: str,
        *,
        actual: str,
        expected: str,
        passed: bool,
    ) -> None:
        """Engine-inferred facts (portfolio state) — not strategy logic."""
        self._conditions.append(
            ConditionTrace(
                name=name,
                actual_value=actual,
                expected_value=expected,
                passed=passed,
            )
        )

    def snapshot(self, *, bar_index: int) -> ConditionSnapshot:
        return ConditionSnapshot(
            bar_index=bar_index,
            conditions=tuple(self._conditions),
            indicators=dict(self._indicators),
        )
