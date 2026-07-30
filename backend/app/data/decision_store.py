"""Columnar storage for the per-bar decision log.

## Layout

One parquet file per run at ``artifacts/{run_id}/decisions.parquet``, matching the
layout ``DataPaths.artifacts`` already documents. Columns are ``bar_index``,
``ts``, the five OHLCV columns, then one column per indicator (``i_``), condition
(``c_``) and operand (``n_``) the run produced. Row groups are written small so a
single-bar read touches one group instead of the file.

Measured on a 194,553-bar ABB 5-minute run of ``ema_crossover``: **16.9 bytes per
bar**, so the complete log is ~3.3 MB against ~315 MB for the same information as
JSON explain events. Single-bar reads land in under 3 ms without deserialising
the file.

## Why writes go through part files

Parquet fixes its schema when the writer opens, but a run does not know its full
column set until it ends: risk operands only appear once a position is open, and
that may be tens of thousands of bars in. Buffering every row to learn the schema
would defeat the point of streaming.

So batches are written as numbered part files, each self-describing, and
consolidated into the single final file on ``close`` once the union of columns is
known. Consolidation streams part-by-part, so peak memory stays at one batch
either way.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Literal

import polars as pl

from app.domain.decisions import (
    BAR_INDEX_COLUMN,
    CONDITION_PREFIX,
    FIXED_COLUMNS,
    INDICATOR_PREFIX,
    OHLCV_COLUMNS,
    OPERAND_PREFIX,
    TIMESTAMP_COLUMN,
    BarDecision,
    DecisionSchema,
)

#: Rows buffered before a part file is written. At ~20 columns this is a few
#: hundred KB in memory - small enough to be irrelevant, large enough that a
#: multi-million-bar run does not produce thousands of parts.
BATCH_ROWS = 25_000

#: Small row groups keep a single-bar read from scanning the whole file.
ROW_GROUP_SIZE = 4_096

#: zstd measured 1.7x smaller than snappy on real decision data, and the read
#: path is predicate-pushdown rather than full scan, so decompression cost is
#: paid on one row group at a time.
COMPRESSION: Literal["zstd"] = "zstd"

_PARTS_DIRNAME = "_decision_parts"


class ParquetDecisionSink:
    """Streams :class:`BarDecision` rows to a parquet artifact.

    Implements the ``DecisionSink`` Protocol. Constructed by the service layer
    with the run's artifact path; the engine only ever sees the Protocol.
    """

    def __init__(self, path: Path, *, batch_rows: int = BATCH_ROWS) -> None:
        self.path = path
        self._batch_rows = batch_rows
        self._buffer: list[dict[str, float | int | bool | None]] = []
        self._parts: list[Path] = []
        self._parts_dir = path.parent / _PARTS_DIRNAME
        self._rows = 0
        self._closed = False

    @property
    def rows(self) -> int:
        return self._rows

    def write(self, decision: BarDecision) -> None:
        row: dict[str, float | int | bool | None] = {
            BAR_INDEX_COLUMN: decision.bar_index,
            TIMESTAMP_COLUMN: decision.timestamp_ms,
            "open": decision.open,
            "high": decision.high,
            "low": decision.low,
            "close": decision.close,
            "volume": decision.volume,
        }
        for name, value in decision.indicators.items():
            row[f"{INDICATOR_PREFIX}{name}"] = value
        for name, passed in decision.conditions.items():
            row[f"{CONDITION_PREFIX}{name}"] = passed
        for name, value in decision.operands.items():
            row[f"{OPERAND_PREFIX}{name}"] = value
        self._buffer.append(row)
        self._rows += 1
        if len(self._buffer) >= self._batch_rows:
            self._flush()

    def close(self, schema: DecisionSchema) -> None:
        if self._closed:
            return
        self._closed = True
        self._flush()
        if not self._parts:
            # A run that produced no bars still gets a file, so readers can
            # distinguish "logged nothing" from "never logged".
            self.path.parent.mkdir(parents=True, exist_ok=True)
            _empty_frame(schema).write_parquet(self.path, compression=COMPRESSION)
            return
        try:
            self._consolidate(schema)
        finally:
            shutil.rmtree(self._parts_dir, ignore_errors=True)

    def _flush(self) -> None:
        if not self._buffer:
            return
        self._parts_dir.mkdir(parents=True, exist_ok=True)
        part = self._parts_dir / f"part-{len(self._parts):05d}.parquet"
        pl.DataFrame(self._buffer, infer_schema_length=None).write_parquet(
            part, compression=COMPRESSION
        )
        self._parts.append(part)
        self._buffer = []

    def _consolidate(self, schema: DecisionSchema) -> None:
        """Merge part files into one, in the schema's declared column order.

        Concatenated diagonally because the parts genuinely disagree on columns:
        a plain multi-file scan takes its schema from the first file and then
        rejects a later part that carries a column the first one had never seen -
        which is exactly what happens the moment a position opens and the risk
        operands start being recorded.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        scan = pl.concat(
            [pl.scan_parquet(part) for part in self._parts],
            how="diagonal_relaxed",
        )
        present = set(scan.collect_schema())
        known = set(schema.columns)
        # Both directions have to be handled. A schema column no batch ever wrote
        # (a condition the strategy declared but never reached) is absent from the
        # parts and must be materialised as nulls; a column the parts have but the
        # schema does not would otherwise be dropped by the select.
        columns = [*schema.columns, *(name for name in present if name not in known)]
        frame = scan.select(
            [
                pl.col(name)
                if name in present
                else pl.lit(None, dtype=_column_dtype(name)).alias(name)
                for name in columns
            ]
        )
        frame.sort(BAR_INDEX_COLUMN).sink_parquet(
            self.path,
            compression=COMPRESSION,
            row_group_size=ROW_GROUP_SIZE,
        )


def _column_dtype(name: str) -> pl.DataType:
    """The dtype a column must have even when no batch supplied a value.

    Typed rather than left to inference: an all-null condition column read back as
    Null instead of Boolean would make "declared but never reached" unreadable as
    a verdict, which is the one thing that column exists to say.
    """
    if name == BAR_INDEX_COLUMN or name == TIMESTAMP_COLUMN:
        return pl.Int64()
    if name.startswith(CONDITION_PREFIX):
        return pl.Boolean()
    return pl.Float64()


def _empty_frame(schema: DecisionSchema) -> pl.DataFrame:
    dtypes: dict[str, pl.DataType] = {
        BAR_INDEX_COLUMN: pl.Int64(),
        TIMESTAMP_COLUMN: pl.Int64(),
    }
    for name in OHLCV_COLUMNS:
        dtypes[name] = pl.Float64()
    for name in schema.indicators:
        dtypes[f"{INDICATOR_PREFIX}{name}"] = pl.Float64()
    for condition in schema.conditions:
        dtypes[condition.column] = pl.Boolean()
    for operand in schema.operands:
        dtypes[operand.column] = pl.Float64()
    return pl.DataFrame(schema={name: dtype for name, dtype in dtypes.items()})


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def log_exists(path: Path) -> bool:
    return path.is_file()


def row_count(path: Path) -> int:
    """Bars in the log, read from parquet metadata rather than the rows."""
    if not path.is_file():
        return 0
    return int(pl.scan_parquet(path).select(pl.len()).collect().item())


def read_window(path: Path, *, start: int, count: int) -> list[dict[str, Any]]:
    """Bars ``[start, start + count)`` in bar order.

    Filtered rather than sliced so the predicate pushes into parquet and only the
    covering row groups are read.
    """
    if not path.is_file() or count <= 0:
        return []
    frame = (
        pl.scan_parquet(path)
        .filter(
            (pl.col(BAR_INDEX_COLUMN) >= start) & (pl.col(BAR_INDEX_COLUMN) < start + count)
        )
        .sort(BAR_INDEX_COLUMN)
        .collect()
    )
    return frame.to_dicts()


def read_bar(path: Path, bar_index: int) -> dict[str, Any] | None:
    """One bar's full record, or ``None`` when the log has no such bar."""
    rows = read_window(path, start=bar_index, count=1)
    return rows[0] if rows else None


def condition_summary(path: Path, schema: DecisionSchema) -> list[dict[str, Any]]:
    """Per-condition evaluated/passed counts over the whole log.

    This is the "why did nothing happen" table: a condition evaluated tens of
    thousands of times with zero passes is the bar the strategy never cleared,
    and it is the first thing to look at on a run that produced no trades.
    Computed as a columnar aggregate, so it costs one pass over booleans rather
    than a walk over per-bar records.
    """
    if not path.is_file():
        return []
    lazy = pl.scan_parquet(path)
    present = set(lazy.collect_schema())
    definitions = [item for item in schema.conditions if item.column in present]
    if not definitions:
        return []
    aggregates = lazy.select(
        [
            *(
                pl.col(item.column).is_not_null().sum().alias(f"evaluated::{item.name}")
                for item in definitions
            ),
            *(
                pl.col(item.column).fill_null(value=False).sum().alias(f"passed::{item.name}")
                for item in definitions
            ),
        ]
    ).collect()
    row = aggregates.row(0, named=True)
    return [
        {
            "name": item.name,
            "expected": item.expected,
            "evaluated": int(row[f"evaluated::{item.name}"] or 0),
            "passed": int(row[f"passed::{item.name}"] or 0),
        }
        for item in definitions
    ]


def split_columns(
    row: dict[str, Any],
) -> tuple[dict[str, float], dict[str, bool | None], dict[str, float]]:
    """Split one log row back into indicators, conditions and operands."""
    indicators: dict[str, float] = {}
    conditions: dict[str, bool | None] = {}
    operands: dict[str, float] = {}
    for key, value in row.items():
        if key in FIXED_COLUMNS:
            continue
        if key.startswith(INDICATOR_PREFIX):
            if value is not None:
                indicators[key[len(INDICATOR_PREFIX) :]] = float(value)
        elif key.startswith(CONDITION_PREFIX):
            # Preserved as None when unevaluated: a rule that was never consulted
            # is a different fact from one that was consulted and failed.
            conditions[key[len(CONDITION_PREFIX) :]] = None if value is None else bool(value)
        elif key.startswith(OPERAND_PREFIX) and value is not None:
            operands[key[len(OPERAND_PREFIX) :]] = float(value)
    return indicators, conditions, operands
