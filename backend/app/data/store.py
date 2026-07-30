"""Parquet bar storage (ARCHITECTURE.md 1, 2.3).

Row groups are written small on purpose: head/tail preview reads then touch
only the row group(s) they need instead of the whole file, however large the
dataset gets.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

ROW_GROUP_SIZE = 10_000


def write_parquet(df: pl.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(path, row_group_size=ROW_GROUP_SIZE)


def row_count(path: Path) -> int:
    return pq.ParquetFile(path).metadata.num_rows  # type: ignore[no-any-return]


def read_head(path: Path, n: int) -> pl.DataFrame:
    """First ``n`` rows, reading only as many row groups as needed."""
    pf = pq.ParquetFile(path)
    batches: list[pa.RecordBatch] = []
    collected = 0
    for batch in pf.iter_batches(batch_size=n):
        batches.append(batch)
        collected += batch.num_rows
        if collected >= n:
            break
    if not batches:
        return pl.DataFrame()
    table = pa.Table.from_batches(batches)
    return cast(pl.DataFrame, pl.from_arrow(table)).head(n)


def read_tail(path: Path, n: int) -> pl.DataFrame:
    """Last ``n`` rows, reading row groups from the end until enough rows are collected."""
    pf = pq.ParquetFile(path)
    tables: list[pa.Table] = []
    remaining = n
    for i in reversed(range(pf.num_row_groups)):
        group = pf.read_row_group(i)
        tables.insert(0, group)
        remaining -= group.num_rows
        if remaining <= 0:
            break
    if not tables:
        return pl.DataFrame()
    table = pa.concat_tables(tables) if len(tables) > 1 else tables[0]
    return cast(pl.DataFrame, pl.from_arrow(table)).tail(n)


def delete(path: Path) -> None:
    path.unlink(missing_ok=True)
