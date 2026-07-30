"""Generic condition trace model for strategy-agnostic decision inspection.

Strategies optionally publish snapshots via ``ExecutionContext.trace_condition``.
The engine records inferred portfolio facts separately — it never evaluates
strategy logic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConditionTrace:
    """One evaluated condition at a single bar."""

    name: str
    actual_value: str
    expected_value: str
    passed: bool

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "name": self.name,
            "actual_value": self.actual_value,
            "expected_value": self.expected_value,
            "passed": self.passed,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> ConditionTrace:
        return cls(
            name=str(raw["name"]),
            actual_value=str(raw["actual_value"]),
            expected_value=str(raw["expected_value"]),
            passed=bool(raw["passed"]),
        )


@dataclass(frozen=True)
class OperandTrace:
    """One raw number behind a verdict, with its display metadata.

    Kept numeric on purpose. ``ConditionTrace.actual_value`` is prose the
    strategy author wrote ("fast 1020.2934 vs slow 1021.4290"); an operand is the
    float itself, so the decision log can store it in a columnar float column and
    a reader can re-derive the arithmetic instead of parsing a sentence.
    """

    name: str
    value: float
    label: str = ""
    unit: str = ""


@dataclass(frozen=True)
class ConditionSnapshot:
    """All conditions traced on one bar."""

    bar_index: int
    conditions: tuple[ConditionTrace, ...]
    indicators: dict[str, float | str]
    #: Numeric operands traced on this bar. Not included in :meth:`to_metadata`:
    #: operands exist for the columnar decision log, and echoing them into the
    #: per-bar JSON metadata would re-inflate exactly what that log replaced.
    operands: tuple[OperandTrace, ...] = ()

    def to_metadata(self) -> dict[str, object]:
        return {
            "conditions": [condition.to_dict() for condition in self.conditions],
            "indicators": self.indicators,
        }

    @classmethod
    def from_metadata(cls, *, bar_index: int, metadata: dict[str, object]) -> ConditionSnapshot:
        raw_conditions = metadata.get("conditions", [])
        conditions: list[ConditionTrace] = []
        if isinstance(raw_conditions, list):
            for item in raw_conditions:
                if isinstance(item, dict):
                    conditions.append(ConditionTrace.from_dict(item))
        indicators_raw = metadata.get("indicators", {})
        indicators: dict[str, float | str] = {}
        if isinstance(indicators_raw, dict):
            for key, value in indicators_raw.items():
                if isinstance(value, (int, float, str)):
                    indicators[str(key)] = value
        return cls(bar_index=bar_index, conditions=tuple(conditions), indicators=indicators)
