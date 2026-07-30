"""The per-bar decision log: every calculation the engine made, on every bar.

## Why this is not an ``ExplainEvent``

``ExplainEvent`` is a *record-shaped* type: 24 fields, most of them null on any
given event, plus a free-form ``metadata`` dict, serialised to one JSON blob per
run. That shape is right for sparse events — an order fill, a position close, a
run-lifecycle marker — because there are at most a few thousand of them and each
one uses a different subset of the fields.

It is the wrong shape for a fact recorded on *every* bar. Measured on a real
194,553-bar run, the per-bar events cost 1,618 bytes each, of which almost
nothing is information:

* 11 of the 24 fields are null on every per-bar event;
* ``instrument``, ``timeframe``, ``layer``, ``event_type``, ``reason_code`` and
  ``schema_version`` are byte-identical on all 194,553;
* each condition's ``name`` and ``expected_value`` are per-*run* constants
  ("more than 200", "fast above slow after being at or below") repeated per bar;
* ``message`` is prose regenerated per bar and derivable from the rest;
* ``actual_value`` is pre-rendered prose ("fast 1020.2934 vs slow 1021.4290")
  duplicating floats already present in ``indicators``.

That redundancy is why the old collector had to cap itself at 50,000 bars and
warn that the rest of the decision log was dropped.

The fix is to separate the constants from the per-bar facts. :class:`DecisionSchema`
holds everything that is fixed for a run — condition names, their expected-value
strings, the indicator names, the operand names. :class:`BarDecision` holds only
what actually varies per bar: floats and tri-state booleans. Written columnar,
the same run costs **16.9 bytes per bar**, so the full log is ~3.3 MB and nothing
needs truncating. The prose is rendered at read time from the schema.

## Why conditions are tri-state

A condition that was not reached on a bar is not the same fact as a condition
that was reached and failed. ``entry_signal`` is never called while a position is
open, so "Fast EMA Crossed Above Slow EMA" has *no verdict* on those bars — and
"the rule was never consulted" is exactly the answer you need when asking why a
crossover did not produce a trade. ``None`` means not evaluated, and the reader
renders it distinctly from ``False``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

#: Bumped when the columnar layout changes in a way a reader must know about.
DECISION_SCHEMA_VERSION = 1

#: Column-name prefixes. The reader splits on these to recover each group, so
#: they must stay distinct and must not collide with the fixed columns below.
INDICATOR_PREFIX = "i_"
CONDITION_PREFIX = "c_"
OPERAND_PREFIX = "n_"

#: Columns present on every decision log regardless of strategy.
BAR_INDEX_COLUMN = "bar_index"
TIMESTAMP_COLUMN = "ts"
OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")
FIXED_COLUMNS = (BAR_INDEX_COLUMN, TIMESTAMP_COLUMN, *OHLCV_COLUMNS)


@dataclass(frozen=True, slots=True)
class ConditionDefinition:
    """A condition's per-run constants, hoisted out of the per-bar rows.

    ``expected`` is the strategy author's description of what would have made
    the condition pass. It is identical on every bar the condition is evaluated
    on, so it is stored once here rather than 194,553 times.
    """

    name: str
    expected: str

    @property
    def column(self) -> str:
        return f"{CONDITION_PREFIX}{self.name}"


@dataclass(frozen=True, slots=True)
class OperandDefinition:
    """A named number behind a verdict, with enough context to render it.

    Operands are the difference between "Position Size Available: 0" and
    "cash 1000 x 20% / price 995.40 = 0.201, floored to 0". ``unit`` drives
    formatting only; it never affects the stored value.
    """

    name: str
    label: str
    unit: str = ""

    @property
    def column(self) -> str:
        return f"{OPERAND_PREFIX}{self.name}"


@dataclass(frozen=True)
class DecisionSchema:
    """Everything about a run's decision log that does not vary per bar.

    Built incrementally during the first bars of a run (a strategy may not trace
    every condition on bar 1) and frozen into the log's sidecar once the run
    ends. Order is preserved: it is the order the strategy evaluated things in,
    which is the order a reader should display them in.
    """

    version: int = DECISION_SCHEMA_VERSION
    instrument: str | None = None
    timeframe: str | None = None
    indicators: tuple[str, ...] = field(default_factory=tuple)
    conditions: tuple[ConditionDefinition, ...] = field(default_factory=tuple)
    operands: tuple[OperandDefinition, ...] = field(default_factory=tuple)

    @property
    def columns(self) -> tuple[str, ...]:
        """Full column order of the columnar log."""
        return (
            *FIXED_COLUMNS,
            *(f"{INDICATOR_PREFIX}{name}" for name in self.indicators),
            *(definition.column for definition in self.conditions),
            *(definition.column for definition in self.operands),
        )

    def condition(self, name: str) -> ConditionDefinition | None:
        for definition in self.conditions:
            if definition.name == name:
                return definition
        return None

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "instrument": self.instrument,
            "timeframe": self.timeframe,
            "indicators": list(self.indicators),
            "conditions": [
                {"name": item.name, "expected": item.expected} for item in self.conditions
            ],
            "operands": [
                {"name": item.name, "label": item.label, "unit": item.unit}
                for item in self.operands
            ],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> DecisionSchema:
        raw_conditions = raw.get("conditions") or []
        raw_operands = raw.get("operands") or []
        raw_indicators = raw.get("indicators") or []
        conditions: list[ConditionDefinition] = []
        if isinstance(raw_conditions, Sequence):
            for item in raw_conditions:
                if isinstance(item, Mapping):
                    conditions.append(
                        ConditionDefinition(
                            name=str(item.get("name", "")),
                            expected=str(item.get("expected", "")),
                        )
                    )
        operands: list[OperandDefinition] = []
        if isinstance(raw_operands, Sequence):
            for item in raw_operands:
                if isinstance(item, Mapping):
                    operands.append(
                        OperandDefinition(
                            name=str(item.get("name", "")),
                            label=str(item.get("label", "")),
                            unit=str(item.get("unit", "")),
                        )
                    )
        indicators: tuple[str, ...] = ()
        if isinstance(raw_indicators, Sequence) and not isinstance(raw_indicators, str):
            indicators = tuple(str(name) for name in raw_indicators)
        version_raw = raw.get("version", DECISION_SCHEMA_VERSION)
        instrument_raw = raw.get("instrument")
        timeframe_raw = raw.get("timeframe")
        return cls(
            version=int(version_raw) if isinstance(version_raw, (int, str)) else 1,
            instrument=None if instrument_raw is None else str(instrument_raw),
            timeframe=None if timeframe_raw is None else str(timeframe_raw),
            indicators=indicators,
            conditions=tuple(conditions),
            operands=tuple(operands),
        )


@dataclass(frozen=True, slots=True)
class BarDecision:
    """Every calculation recorded on one bar.

    ``conditions`` is tri-state per the module docstring: a name absent from the
    mapping was not evaluated on this bar. ``operands`` carries the raw numbers
    behind the verdicts — never pre-formatted prose, so a reader can re-derive
    the arithmetic rather than parse a sentence.
    """

    bar_index: int
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    indicators: Mapping[str, float] = field(default_factory=dict)
    conditions: Mapping[str, bool] = field(default_factory=dict)
    operands: Mapping[str, float] = field(default_factory=dict)


class DecisionSink(Protocol):
    """Where the engine sends per-bar decisions.

    A Protocol rather than a concrete writer because the engine must not do
    artifact I/O: ``app.engine`` depends only on ``app.domain``, and the parquet
    implementation lives in ``app.data`` where the columnar dependencies belong.
    The engine streams rows through this interface as it goes, so a
    multi-million-bar run never materialises its own decision log in memory —
    the same guarantee ``BarIterator`` makes about bars.
    """

    def write(self, decision: BarDecision) -> None:
        """Record one bar. Called at most once per bar, in bar order."""
        ...

    def close(self, schema: DecisionSchema) -> None:
        """Finalise the log. ``schema`` is complete only once the run has ended."""
        ...


class NullDecisionSink:
    """Discards everything. The default when no decision log was requested."""

    __slots__ = ("rows",)

    def __init__(self) -> None:
        self.rows = 0

    def write(self, decision: BarDecision) -> None:
        self.rows += 1

    def close(self, schema: DecisionSchema) -> None:
        return None


class MemoryDecisionSink:
    """Keeps decisions in a list. For tests and small ad-hoc runs only."""

    __slots__ = ("decisions", "schema")

    def __init__(self) -> None:
        self.decisions: list[BarDecision] = []
        self.schema = DecisionSchema()

    @property
    def rows(self) -> int:
        return len(self.decisions)

    def write(self, decision: BarDecision) -> None:
        self.decisions.append(decision)

    def close(self, schema: DecisionSchema) -> None:
        self.schema = schema
