"""The per-bar decision log records every calculation, on every bar.

What these pin down is that the log is *complete* - uncapped in length and
carrying the arithmetic behind each verdict, not only the verdict. Both were
missing before: the old per-bar events stopped at 50,000 bars and recorded
"Position Size Available: 0" with no way to tell a floored size from a rule that
declined to size at all.
"""

from __future__ import annotations

from app.domain.conditions import ConditionSnapshot, ConditionTrace, OperandTrace
from app.domain.decisions import (
    DECISION_SCHEMA_VERSION,
    DecisionSchema,
    MemoryDecisionSink,
    NullDecisionSink,
)
from app.domain.explain import ExplainLevel
from app.engine.bars import Bar, BarIterator
from app.engine.explain.collector import MAX_PER_BAR_EXPLAIN_EVENTS
from app.engine.explain.decision_log import DecisionRecorder
from app.engine.runner import ExecutionConfig, ExecutionEngine

TRACING_STRATEGY = """
class Strategy:
    def on_bar(self, bar):
        self.ctx.trace_indicator("price", bar.close)
        self.ctx.trace_condition(
            "Close Above 100",
            actual=str(bar.close),
            expected="above 100",
            passed=bar.close > 100,
        )
        self.ctx.trace_operand("close", bar.close, label="Close", unit="rupees")
"""


def _bar(index: int, *, close: float | None = None) -> Bar:
    price = 100.0 + index if close is None else close
    return Bar(
        ts=1_000 + index * 1_000,
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
        volume=10.0,
    )


def _snapshot(bar_index: int, *, passed: bool = True) -> ConditionSnapshot:
    return ConditionSnapshot(
        bar_index=bar_index,
        conditions=(
            ConditionTrace(
                name="Warmup Complete",
                actual_value=f"{bar_index} bars",
                expected_value="more than 2",
                passed=passed,
            ),
        ),
        indicators={"sma": 101.5},
        operands=(OperandTrace(name="cash", value=1000.0, label="Cash", unit="rupees"),),
    )


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------


def test_recorder_streams_rows_and_counts_them() -> None:
    sink = MemoryDecisionSink()
    recorder = DecisionRecorder(sink, instrument="NIFTY", timeframe="5m")

    for index in range(3):
        recorder.record(_snapshot(index), bar=_bar(index), bar_index=index)

    assert recorder.rows == 3
    assert [decision.bar_index for decision in sink.decisions] == [0, 1, 2]
    assert sink.decisions[0].close == 100.0
    assert sink.decisions[0].indicators == {"sma": 101.5}
    assert sink.decisions[0].operands == {"cash": 1000.0}


def test_recorder_hoists_per_run_constants_into_the_schema() -> None:
    """Condition names and expected prose are identical per bar, so stored once."""
    sink = MemoryDecisionSink()
    recorder = DecisionRecorder(sink, instrument="NIFTY", timeframe="5m")
    for index in range(5):
        recorder.record(_snapshot(index), bar=_bar(index), bar_index=index)

    schema = recorder.finish()

    assert schema.version == DECISION_SCHEMA_VERSION
    assert schema.instrument == "NIFTY"
    assert schema.timeframe == "5m"
    assert [item.name for item in schema.conditions] == ["Warmup Complete"]
    assert schema.conditions[0].expected == "more than 2"
    assert [item.name for item in schema.operands] == ["cash"]
    assert schema.operands[0].label == "Cash"
    assert schema.operands[0].unit == "rupees"
    assert schema.indicators == ("sma",)
    # The rows themselves carry no copy of any of that.
    assert sink.schema == schema


def test_schema_learns_columns_that_only_appear_late() -> None:
    """Risk operands first appear when a position opens, possibly bars in."""
    sink = MemoryDecisionSink()
    recorder = DecisionRecorder(sink)
    recorder.record(_snapshot(0), bar=_bar(0), bar_index=0)
    late = ConditionSnapshot(
        bar_index=1,
        conditions=(
            ConditionTrace(
                name="Risk Exit Triggered",
                actual_value="none",
                expected_value="any protective rule",
                passed=False,
            ),
        ),
        indicators={},
        operands=(OperandTrace(name="risk_stop_level", value=98.0, label="Stop level"),),
    )
    recorder.record(late, bar=_bar(1), bar_index=1)

    schema = recorder.finish()

    assert [item.name for item in schema.conditions] == ["Warmup Complete", "Risk Exit Triggered"]
    assert [item.name for item in schema.operands] == ["cash", "risk_stop_level"]


def test_a_condition_absent_on_a_bar_is_not_recorded_as_failed() -> None:
    """Never consulted and consulted-then-failed are different facts."""
    sink = MemoryDecisionSink()
    recorder = DecisionRecorder(sink)
    recorder.record(_snapshot(0, passed=False), bar=_bar(0), bar_index=0)
    recorder.record(
        ConditionSnapshot(bar_index=1, conditions=(), indicators={}, operands=()),
        bar=_bar(1),
        bar_index=1,
    )

    assert sink.decisions[0].conditions == {"Warmup Complete": False}
    assert sink.decisions[1].conditions == {}


def test_non_numeric_indicators_are_dropped_from_the_columnar_log() -> None:
    sink = MemoryDecisionSink()
    recorder = DecisionRecorder(sink)
    recorder.record(
        ConditionSnapshot(
            bar_index=0,
            conditions=(),
            indicators={"session": "Regular", "sma": 12.5},
            operands=(),
        ),
        bar=_bar(0),
        bar_index=0,
    )

    assert sink.decisions[0].indicators == {"sma": 12.5}


def test_null_sink_discards_without_retaining() -> None:
    sink = NullDecisionSink()
    recorder = DecisionRecorder(sink)
    for index in range(10):
        recorder.record(_snapshot(index), bar=_bar(index), bar_index=index)
    recorder.finish()

    assert sink.rows == 10


# ---------------------------------------------------------------------------
# Through the bar loop
# ---------------------------------------------------------------------------


def test_the_engine_logs_every_bar_it_replays() -> None:
    sink = MemoryDecisionSink()
    bars = BarIterator([_bar(index) for index in range(40)])

    result = ExecutionEngine(ExecutionConfig(explain_level=ExplainLevel.FULL)).run(
        bars=bars,
        strategy_source=TRACING_STRATEGY,
        decision_sink=sink,
    )

    assert result.errors == ()
    assert result.decision_rows == 40
    assert len(sink.decisions) == 40
    assert result.decision_schema is not None
    assert [item.name for item in result.decision_schema.conditions] == [
        "Close Above 100",
        "Already In Position",
        "Pending Orders After Bar",
    ]


def test_the_log_is_not_capped_where_the_json_events_were() -> None:
    """The 50,000-bar ceiling was a property of the JSON encoding, not the log."""
    bar_count = MAX_PER_BAR_EXPLAIN_EVENTS + 1_000
    sink = MemoryDecisionSink()

    result = ExecutionEngine(ExecutionConfig(explain_level=ExplainLevel.FULL)).run(
        bars=BarIterator.streaming((_bar(index) for index in range(bar_count)), count=bar_count),
        strategy_source=TRACING_STRATEGY,
        decision_sink=sink,
    )

    assert result.decision_rows == bar_count
    assert len(sink.decisions) == bar_count
    assert sink.decisions[-1].bar_index == bar_count - 1


def test_conditions_are_not_duplicated_into_the_json_events() -> None:
    """Echoing them cost ~1.6 KB per bar and is what forced the cap."""
    sink = MemoryDecisionSink()

    with_log = ExecutionEngine(ExecutionConfig(explain_level=ExplainLevel.FULL)).run(
        bars=BarIterator([_bar(index) for index in range(30)]),
        strategy_source=TRACING_STRATEGY,
        decision_sink=sink,
    )
    without_log = ExecutionEngine(ExecutionConfig(explain_level=ExplainLevel.FULL)).run(
        bars=BarIterator([_bar(index) for index in range(30)]),
        strategy_source=TRACING_STRATEGY,
    )

    condition_events = [
        event
        for event in with_log.explain_events
        if event.event_type.value == "conditions_evaluated"
    ]
    assert condition_events == []
    # Without a sink the old path still fills the Decision Inspector.
    assert any(
        event.event_type.value == "conditions_evaluated" for event in without_log.explain_events
    )


def test_the_sink_is_closed_even_when_the_strategy_fails_to_compile() -> None:
    sink = MemoryDecisionSink()

    result = ExecutionEngine(ExecutionConfig(explain_level=ExplainLevel.FULL)).run(
        bars=BarIterator([_bar(0)]),
        strategy_source="this is not python(",
        decision_sink=sink,
    )

    assert result.completed is False
    assert result.decision_rows == 0
    # close() ran, so the schema was handed over rather than left unset.
    assert sink.schema == DecisionSchema(instrument=None, timeframe=None)
