"""Reading stored bars back off disk.

This is the only place Parquet is read for a run. The engine receives plain
rows from here, which is what lets it stay importable without polars, pyarrow
or a database (ARCHITECTURE.md principle 3).

Bars are read into a *columnar* frame and streamed out of it one row at a time.
The distinction matters more than it looks: as six float64 columns a bar costs
about 48 bytes, and as a Python dict about ten times that. Materialising every
row up front is what made a multi-year intraday dataset a multi-gigabyte replay.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import polars as pl

from app.data.bars_validator import validate_bar_frame
from app.data.schema import CANONICAL_COLUMNS

#: Rows converted to dicts at a time while streaming. Large enough that the
#: per-slice overhead disappears, small enough that the transient stays flat
#: however long the dataset is.
BAR_STREAM_CHUNK = 8_192


def load_bar_frame(path: Path) -> pl.DataFrame:
    """Read, order and validate the stored bars, still columnar.

    Sorting here rather than trusting the file is cheap insurance: the whole
    engine assumes chronological order, and a run against silently unsorted
    bars would produce results that look plausible and are wrong.
    """
    frame = pl.read_parquet(path, columns=list(CANONICAL_COLUMNS)).sort("ts")
    validate_bar_frame(frame)
    return frame


def iter_bar_rows(frame: pl.DataFrame, *, limit: int | None = None) -> Iterator[dict[str, Any]]:
    """Stream canonical row mappings, oldest first, without materialising them all.

    Only ``BAR_STREAM_CHUNK`` rows exist as Python objects at any moment, so the
    caller decides how much of the series it keeps - the loader keeps none.
    """
    height = frame.height if limit is None else max(0, min(limit, frame.height))
    if height == 0:
        return
    for chunk in frame.head(height).iter_slices(BAR_STREAM_CHUNK):
        yield from chunk.iter_rows(named=True)


def bar_timestamp_at(frame: pl.DataFrame, index: int) -> int:
    """One bar's timestamp by position, read straight off the column."""
    return int(frame["ts"][index])


def load_bars(path: Path) -> list[dict[str, Any]]:
    """Every bar as a plain row mapping, ordered oldest-first.

    Materialises the whole series. Prefer :func:`load_bar_frame` with
    :func:`iter_bar_rows` on any path that replays a full dataset.
    """
    return list(iter_bar_rows(load_bar_frame(path)))
