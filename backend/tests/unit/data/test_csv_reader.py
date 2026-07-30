"""CSV header validation - the one thing app.data.readers.csv_reader is allowed to raise on."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.data.errors import MissingColumnsError
from app.data.readers.csv_reader import read_csv


def test_reads_required_columns_case_insensitively(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv"
    path.write_text("Timestamp,Open,High,Low,Close,Volume\n2024-01-01 09:15:00,1,2,3,4,5\n")

    df = read_csv(path)

    assert df.columns == ["timestamp", "open", "high", "low", "close", "volume"]
    assert df.height == 1


def test_extra_columns_are_dropped(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv"
    path.write_text(
        "timestamp,open,high,low,close,volume,extra\n2024-01-01 09:15:00,1,2,3,4,5,ignored\n"
    )

    df = read_csv(path)

    assert df.columns == ["timestamp", "open", "high", "low", "close", "volume"]


def test_missing_required_column_raises(tmp_path: Path) -> None:
    path = tmp_path / "bars.csv"
    path.write_text("timestamp,open,high,low,close\n2024-01-01 09:15:00,1,2,3,4\n")

    with pytest.raises(MissingColumnsError) as exc_info:
        read_csv(path)

    assert "volume" in str(exc_info.value)
