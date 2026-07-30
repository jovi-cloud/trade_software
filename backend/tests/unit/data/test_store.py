"""Parquet head/tail reads return the right rows without reading the whole file."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from app.data import store


def _bars(n: int) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ts": list(range(n)),
            "open": [float(i) for i in range(n)],
            "high": [float(i) for i in range(n)],
            "low": [float(i) for i in range(n)],
            "close": [float(i) for i in range(n)],
            "volume": [1.0] * n,
        }
    )


def test_write_then_row_count(tmp_path: Path) -> None:
    path = tmp_path / "bars.parquet"
    store.write_parquet(_bars(50), path)

    assert store.row_count(path) == 50


def test_read_head_returns_first_n_rows_in_order(tmp_path: Path) -> None:
    path = tmp_path / "bars.parquet"
    store.write_parquet(_bars(100), path)

    head = store.read_head(path, 5)

    assert head["ts"].to_list() == [0, 1, 2, 3, 4]


def test_read_tail_returns_last_n_rows_in_order(tmp_path: Path) -> None:
    path = tmp_path / "bars.parquet"
    store.write_parquet(_bars(100), path)

    tail = store.read_tail(path, 5)

    assert tail["ts"].to_list() == [95, 96, 97, 98, 99]


def test_read_head_and_tail_span_multiple_row_groups(tmp_path: Path) -> None:
    """Row groups are small on purpose - exercise the multi-group path directly."""
    path = tmp_path / "bars.parquet"
    store.write_parquet(_bars(35_000), path)

    head = store.read_head(path, 20)
    tail = store.read_tail(path, 20)

    assert head["ts"].to_list() == list(range(20))
    assert tail["ts"].to_list() == list(range(34_980, 35_000))


def test_delete_removes_file(tmp_path: Path) -> None:
    path = tmp_path / "bars.parquet"
    store.write_parquet(_bars(1), path)

    store.delete(path)

    assert not path.exists()


def test_delete_missing_file_does_not_raise(tmp_path: Path) -> None:
    store.delete(tmp_path / "does-not-exist.parquet")
