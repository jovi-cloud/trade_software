"""Columnar decision-log storage: write, consolidate, read back.

The round-trip matters more than it looks. Rows are written in batches whose
column sets differ (a risk operand only exists once a position is open), so
"write then read the same values back" is the property that the part-file
consolidation must not break.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.data.decision_store import (
    ParquetDecisionSink,
    condition_summary,
    log_exists,
    read_bar,
    read_window,
    row_count,
    split_columns,
)
from app.domain.decisions import (
    BarDecision,
    ConditionDefinition,
    DecisionSchema,
    OperandDefinition,
)

SCHEMA = DecisionSchema(
    instrument="ABB",
    timeframe="5m",
    indicators=("ema_fast", "ema_slow"),
    conditions=(
        ConditionDefinition(name="Entry Rules Met", expected="an entry signal"),
        ConditionDefinition(name="Position Size Available", expected="greater than zero"),
    ),
    operands=(
        OperandDefinition(name="size_capital", label="Capital available"),
        OperandDefinition(name="size_raw_quantity", label="Size before rounding", unit="units"),
    ),
)


def _decision(index: int, **overrides: object) -> BarDecision:
    payload: dict[str, object] = {
        "bar_index": index,
        "timestamp_ms": 1_000 + index * 1_000,
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 5.0,
        "indicators": {"ema_fast": 100.1, "ema_slow": 100.2},
        "conditions": {"Entry Rules Met": index % 2 == 0},
        "operands": {"size_capital": 1000.0},
    }
    payload.update(overrides)
    return BarDecision(**payload)  # type: ignore[arg-type]


@pytest.fixture
def log_path(tmp_path: Path) -> Path:
    return tmp_path / "artifacts" / "run-1" / "decisions.parquet"


def test_write_and_read_one_bar(log_path: Path) -> None:
    sink = ParquetDecisionSink(log_path)
    sink.write(_decision(0))
    sink.close(SCHEMA)

    assert log_exists(log_path)
    assert row_count(log_path) == 1
    row = read_bar(log_path, 0)
    assert row is not None
    indicators, conditions, operands = split_columns(row)
    assert indicators == {"ema_fast": 100.1, "ema_slow": 100.2}
    assert conditions["Entry Rules Met"] is True
    assert operands == {"size_capital": 1000.0}


def test_a_window_returns_only_the_requested_bars_in_order(log_path: Path) -> None:
    sink = ParquetDecisionSink(log_path)
    for index in range(50):
        sink.write(_decision(index))
    sink.close(SCHEMA)

    rows = read_window(log_path, start=10, count=5)

    assert [row["bar_index"] for row in rows] == [10, 11, 12, 13, 14]


def test_batching_across_part_files_preserves_every_row(log_path: Path) -> None:
    """Small batch size forces several parts, which must consolidate losslessly."""
    sink = ParquetDecisionSink(log_path, batch_rows=7)
    for index in range(30):
        sink.write(_decision(index))
    sink.close(SCHEMA)

    assert row_count(log_path) == 30
    rows = read_window(log_path, start=0, count=30)
    assert [row["bar_index"] for row in rows] == list(range(30))
    assert not (log_path.parent / "_decision_parts").exists()


def test_a_column_appearing_only_in_a_later_batch_survives(log_path: Path) -> None:
    """Risk operands start mid-run, after the first part file is already written."""
    sink = ParquetDecisionSink(log_path, batch_rows=5)
    for index in range(5):
        sink.write(_decision(index))
    for index in range(5, 10):
        sink.write(_decision(index, operands={"size_capital": 1000.0, "risk_stop_level": 98.0}))
    sink.close(
        DecisionSchema(
            indicators=SCHEMA.indicators,
            conditions=SCHEMA.conditions,
            operands=(
                *SCHEMA.operands,
                OperandDefinition(name="risk_stop_level", label="Stop level"),
            ),
        )
    )

    early = read_bar(log_path, 0)
    late = read_bar(log_path, 7)
    assert early is not None and late is not None
    assert "risk_stop_level" not in split_columns(early)[2]
    assert split_columns(late)[2]["risk_stop_level"] == 98.0


def test_an_unevaluated_condition_reads_back_as_none_not_false(log_path: Path) -> None:
    sink = ParquetDecisionSink(log_path)
    sink.write(_decision(0, conditions={"Entry Rules Met": True}))
    sink.write(_decision(1, conditions={"Entry Rules Met": False}))
    sink.write(_decision(2, conditions={}))
    sink.close(SCHEMA)

    verdicts = [split_columns(row)[1]["Entry Rules Met"] for row in read_window(
        log_path, start=0, count=3
    )]

    assert verdicts == [True, False, None]


def test_condition_summary_tallies_reached_versus_passed(log_path: Path) -> None:
    """The "why did nothing happen" table: reached often, passed never."""
    sink = ParquetDecisionSink(log_path)
    for index in range(10):
        sink.write(
            _decision(
                index,
                conditions={
                    "Entry Rules Met": index < 4,
                    # Only consulted on the bars where entry rules passed, and
                    # never satisfied - the shape of a floored-to-zero run.
                    **({"Position Size Available": False} if index < 4 else {}),
                },
            )
        )
    sink.close(SCHEMA)

    summary = {item["name"]: item for item in condition_summary(log_path, SCHEMA)}

    assert summary["Entry Rules Met"]["evaluated"] == 10
    assert summary["Entry Rules Met"]["passed"] == 4
    assert summary["Position Size Available"]["evaluated"] == 4
    assert summary["Position Size Available"]["passed"] == 0
    assert summary["Position Size Available"]["expected"] == "greater than zero"


def test_a_run_with_no_bars_still_produces_a_readable_log(log_path: Path) -> None:
    """"Logged nothing" must be distinguishable from "never logged"."""
    ParquetDecisionSink(log_path).close(SCHEMA)

    assert log_exists(log_path)
    assert row_count(log_path) == 0
    assert read_window(log_path, start=0, count=10) == []


def test_reads_against_a_missing_log_are_empty_rather_than_raising(tmp_path: Path) -> None:
    missing = tmp_path / "nope" / "decisions.parquet"

    assert log_exists(missing) is False
    assert row_count(missing) == 0
    assert read_bar(missing, 0) is None
    assert condition_summary(missing, SCHEMA) == []


def test_closing_twice_does_not_rewrite_or_raise(log_path: Path) -> None:
    sink = ParquetDecisionSink(log_path)
    sink.write(_decision(0))
    sink.close(SCHEMA)
    sink.close(SCHEMA)

    assert row_count(log_path) == 1


def test_schema_round_trips_through_its_dict_form() -> None:
    restored = DecisionSchema.from_dict(SCHEMA.to_dict())

    assert restored == SCHEMA
    assert restored.columns == SCHEMA.columns
    assert restored.condition("Position Size Available") is not None
