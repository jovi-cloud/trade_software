"""The loader reads bars columnar and streams them out one row at a time."""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from app.data.errors import InvalidBarsError
from app.data.loader import (
    BAR_STREAM_CHUNK,
    bar_timestamp_at,
    iter_bar_rows,
    load_bar_frame,
    load_bars,
)


def _write_parquet(path: Path, count: int, *, shuffled: bool = False) -> Path:
    timestamps = list(range(count))
    if shuffled:
        timestamps = timestamps[::-1]
    frame = pl.DataFrame(
        {
            "ts": timestamps,
            "open": [100.0 + index for index in range(count)],
            "high": [101.0 + index for index in range(count)],
            "low": [99.0 + index for index in range(count)],
            "close": [100.5 + index for index in range(count)],
            "volume": [1_000.0] * count,
        }
    )
    target = path / "bars.parquet"
    frame.write_parquet(target)
    return target


def test_the_frame_is_ordered_oldest_first_whatever_the_file_says(tmp_path: Path) -> None:
    path = _write_parquet(tmp_path, 20, shuffled=True)

    frame = load_bar_frame(path)

    assert frame["ts"].to_list() == sorted(frame["ts"].to_list())


def test_streaming_yields_every_row_in_order(tmp_path: Path) -> None:
    path = _write_parquet(tmp_path, 100)

    rows = list(iter_bar_rows(load_bar_frame(path)))

    assert len(rows) == 100
    assert [row["ts"] for row in rows] == list(range(100))
    assert set(rows[0]) == {"ts", "open", "high", "low", "close", "volume"}


def test_streaming_spans_more_than_one_chunk(tmp_path: Path) -> None:
    """Chunk boundaries must not drop or duplicate a bar."""
    count = BAR_STREAM_CHUNK + 137
    path = _write_parquet(tmp_path, count)

    timestamps = [row["ts"] for row in iter_bar_rows(load_bar_frame(path))]

    assert timestamps == list(range(count))


def test_a_limit_takes_a_prefix(tmp_path: Path) -> None:
    path = _write_parquet(tmp_path, 50)
    frame = load_bar_frame(path)

    assert [row["ts"] for row in iter_bar_rows(frame, limit=5)] == [0, 1, 2, 3, 4]
    assert len(list(iter_bar_rows(frame, limit=0))) == 0
    # A limit past the end is not an error; the dataset simply ends.
    assert len(list(iter_bar_rows(frame, limit=500))) == 50


def test_the_frame_is_reusable_while_the_stream_is_not(tmp_path: Path) -> None:
    """The frame is the retained copy, so it must survive being streamed twice."""
    path = _write_parquet(tmp_path, 10)
    frame = load_bar_frame(path)

    assert len(list(iter_bar_rows(frame))) == 10
    assert len(list(iter_bar_rows(frame))) == 10


def test_timestamps_are_read_by_position_without_materialising_rows(tmp_path: Path) -> None:
    path = _write_parquet(tmp_path, 30)
    frame = load_bar_frame(path)

    assert bar_timestamp_at(frame, 0) == 0
    assert bar_timestamp_at(frame, frame.height - 1) == 29


def test_an_empty_file_is_rejected_before_any_replay(tmp_path: Path) -> None:
    path = _write_parquet(tmp_path, 0)

    with pytest.raises(InvalidBarsError, match="no bars"):
        load_bar_frame(path)


def test_load_bars_still_returns_the_whole_series(tmp_path: Path) -> None:
    path = _write_parquet(tmp_path, 12)

    rows = load_bars(path)

    assert len(rows) == 12
    assert [row["ts"] for row in rows] == list(range(12))
