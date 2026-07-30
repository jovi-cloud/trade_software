"""Dataset validator tests."""

from __future__ import annotations

import polars as pl
import pytest

from app.data.errors import InvalidBarsError
from app.data.validator import validate_and_clean
from app.domain.enums import Timeframe


def _raw_frame(rows: list[dict[str, object]]) -> pl.DataFrame:
    return pl.DataFrame(rows)


def test_validate_and_clean_rejects_ohlc_violations() -> None:
    raw = _raw_frame(
        [
            {
                "timestamp": "2024-01-01 09:15:00",
                "open": "100",
                "high": "99",
                "low": "101",
                "close": "100",
                "volume": "10",
            }
        ]
    )
    bars, report = validate_and_clean(raw, Timeframe.M1)
    assert bars.height == 0
    assert report.ohlc_violations == 1


def test_validate_and_clean_rejects_negative_volume() -> None:
    raw = _raw_frame(
        [
            {
                "timestamp": "2024-01-01 09:15:00",
                "open": "100",
                "high": "101",
                "low": "99",
                "close": "100",
                "volume": "-1",
            }
        ]
    )
    bars, report = validate_and_clean(raw, Timeframe.M1)
    assert bars.height == 0
    assert report.negative_volumes == 1


def test_validate_bars_strict_raises_on_duplicate_timestamps() -> None:
    from app.data.bars_validator import validate_bars_strict

    rows = [
        {"ts": 1, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10.0},
        {"ts": 1, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10.0},
    ]
    with pytest.raises(InvalidBarsError):
        validate_bars_strict(rows)
