"""Tests for schema and OHLC validation."""

from __future__ import annotations

import polars as pl

from app.data.data_pipeline.validators import validate_and_normalise
from app.domain.enums import Timeframe


def test_validate_accepts_valid_rows(valid_df: pl.DataFrame) -> None:
    bars, report = validate_and_normalise(valid_df, timeframe=Timeframe.M1)
    assert report.valid_rows == 3
    assert bars.height == 3
    assert bars.columns == ["ts", "open", "high", "low", "close", "volume"]


def test_validate_rejects_incomplete_numeric_data() -> None:
    df = pl.DataFrame(
        {
            "timestamp": ["2024-01-01 09:15:00"],
            "open": ["1"],
            "high": ["2"],
            "low": ["0.5"],
            "close": [""],
            "volume": ["100"],
        }
    )
    _, report = validate_and_normalise(df, timeframe=Timeframe.M1)
    assert report.valid_rows == 0
    assert report.invalid_prices >= 1


def test_validate_rejects_invalid_timestamps(valid_df: pl.DataFrame) -> None:
    df = valid_df.with_columns(pl.Series("timestamp", ["bad", "2024-01-01 09:16:00", "2024-01-01 09:17:00"]))
    _, report = validate_and_normalise(df, timeframe=Timeframe.M1)
    assert report.invalid_dates == 1


def test_validate_rejects_duplicate_timestamps(valid_df: pl.DataFrame) -> None:
    df = valid_df.with_columns(
        pl.Series("timestamp", ["2024-01-01 09:15:00", "2024-01-01 09:15:00", "2024-01-01 09:17:00"])
    )
    _, report = validate_and_normalise(df, timeframe=Timeframe.M1)
    assert report.duplicate_timestamps == 1


def test_validate_sorts_out_of_order_rows(valid_df: pl.DataFrame) -> None:
    df = valid_df[[2, 0, 1]]
    bars, report = validate_and_normalise(df, timeframe=Timeframe.M1)
    assert report.out_of_order_timestamps > 0
    assert bars.select("ts").to_series().is_sorted()


def test_validate_rejects_negative_prices(valid_df: pl.DataFrame) -> None:
    df = valid_df.with_columns(pl.Series("low", ["-1", "100", "101"]))
    _, report = validate_and_normalise(df, timeframe=Timeframe.M1)
    assert report.non_positive_prices >= 1


def test_validate_rejects_invalid_ohlc(valid_df: pl.DataFrame) -> None:
    df = valid_df.with_columns(pl.Series("high", ["98", "102", "103"]))
    _, report = validate_and_normalise(df, timeframe=Timeframe.M1)
    assert report.ohlc_violations == 1


def test_validate_rejects_negative_volume(valid_df: pl.DataFrame) -> None:
    df = valid_df.with_columns(pl.Series("volume", ["-100", "1200", "900"]))
    _, report = validate_and_normalise(df, timeframe=Timeframe.M1)
    assert report.negative_volumes == 1
