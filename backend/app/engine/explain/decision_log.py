"""Stream per-bar decisions into a :class:`DecisionSink`.

The recorder is the seam between the bar loop and wherever the decision log is
being written. It holds no rows: each bar is converted, handed to the sink and
forgotten, so a multi-million-bar run costs a constant amount of memory here
regardless of how long the log gets. That is the whole reason the old 50,000-bar
cap existed and the whole reason it no longer needs to.

Schema accumulation happens as a side effect of recording. A strategy does not
trace every condition on every bar — ``entry_signal`` is never called while a
position is open, and risk operands only exist while there is a trade to protect
— so the set of columns is only fully known once the run has ended. The recorder
learns names in first-seen order (which is evaluation order, and therefore
display order) and hands the completed schema to the sink on :meth:`finish`.
"""

from __future__ import annotations

from app.domain.conditions import ConditionSnapshot
from app.domain.decisions import (
    BarDecision,
    ConditionDefinition,
    DecisionSchema,
    DecisionSink,
    OperandDefinition,
)
from app.engine.bars import Bar


class DecisionRecorder:
    """Converts per-bar traces into sink writes and builds the run's schema."""

    __slots__ = (
        "_condition_order",
        "_conditions",
        "_indicator_order",
        "_instrument",
        "_operand_order",
        "_operands",
        "_rows",
        "_sink",
        "_timeframe",
    )

    def __init__(
        self,
        sink: DecisionSink,
        *,
        instrument: str | None = None,
        timeframe: str | None = None,
    ) -> None:
        self._sink = sink
        self._instrument = instrument
        self._timeframe = timeframe
        # Insertion-ordered dicts double as ordered sets: first-seen order is
        # evaluation order, which is the order a reader should display.
        self._conditions: dict[str, ConditionDefinition] = {}
        self._operands: dict[str, OperandDefinition] = {}
        self._condition_order: dict[str, None] = {}
        self._indicator_order: dict[str, None] = {}
        self._operand_order: dict[str, None] = {}
        self._rows = 0

    @property
    def rows(self) -> int:
        """Bars recorded so far. Uncapped."""
        return self._rows

    def record(self, snapshot: ConditionSnapshot, *, bar: Bar, bar_index: int) -> None:
        """Record one bar's calculations."""
        indicators: dict[str, float] = {}
        for name, value in snapshot.indicators.items():
            # Indicator channels are float-valued; a strategy publishing a string
            # has nothing a numeric column can hold, so it is dropped from the
            # columnar log rather than silently coerced.
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                indicators[name] = float(value)
                self._indicator_order.setdefault(name, None)

        conditions: dict[str, bool] = {}
        for trace in snapshot.conditions:
            conditions[trace.name] = trace.passed
            self._condition_order.setdefault(trace.name, None)
            # Expected-value prose is a per-run constant. Keep the first one seen:
            # later bars repeat it verbatim, which is precisely why it is hoisted.
            if trace.name not in self._conditions:
                self._conditions[trace.name] = ConditionDefinition(
                    name=trace.name,
                    expected=trace.expected_value,
                )

        operands: dict[str, float] = {}
        for operand in snapshot.operands:
            operands[operand.name] = float(operand.value)
            self._operand_order.setdefault(operand.name, None)
            if operand.name not in self._operands:
                self._operands[operand.name] = OperandDefinition(
                    name=operand.name,
                    label=operand.label or operand.name,
                    unit=operand.unit,
                )

        self._sink.write(
            BarDecision(
                bar_index=bar_index,
                timestamp_ms=bar.ts,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                indicators=indicators,
                conditions=conditions,
                operands=operands,
            )
        )
        self._rows += 1

    def schema(self) -> DecisionSchema:
        """The run's schema as currently known."""
        return DecisionSchema(
            instrument=self._instrument,
            timeframe=self._timeframe,
            indicators=tuple(self._indicator_order),
            conditions=tuple(self._conditions[name] for name in self._condition_order),
            operands=tuple(self._operands[name] for name in self._operand_order),
        )

    def finish(self) -> DecisionSchema:
        """Close the sink with the completed schema and return it."""
        schema = self.schema()
        self._sink.close(schema)
        return schema
