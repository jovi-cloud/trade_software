"""Tests for file import and column mapping."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.data.data_pipeline.importer import detect_format, read_raw
from app.data.errors import MissingColumnsError


def test_detect_format_csv() -> None:
    assert detect_format(Path("data.csv")) == "csv"


def test_detect_format_xlsx() -> None:
    assert detect_format(Path("data.xlsx")) == "xlsx"


def test_detect_format_parquet() -> None:
    assert detect_format(Path("data.parquet")) == "parquet"


def test_read_raw_maps_datetime_column(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv"
    path.write_text(
        "DateTime,Open,High,Low,Close,Volume\n"
        "2024-01-01 09:15:00,100,101,99,100.5,1000\n",
        encoding="utf-8",
    )
    df = read_raw(path)
    assert df.columns == ["timestamp", "open", "high", "low", "close", "volume"]
    assert df.height == 1


def test_read_raw_raises_on_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("timestamp,open\n2024-01-01,1\n", encoding="utf-8")
    with pytest.raises(MissingColumnsError):
        read_raw(path)
