"""Tests for gap detection."""

from __future__ import annotations

import polars as pl

from app.data.data_pipeline.gap_detector import detect_gaps
from app.domain.enums import Timeframe


def _bars(timestamps: list[int]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ts": timestamps,
            "open": [100.0] * len(timestamps),
            "high": [101.0] * len(timestamps),
            "low": [99.0] * len(timestamps),
            "close": [100.0] * len(timestamps),
            "volume": [1000.0] * len(timestamps),
        }
    )


def test_detect_gaps_finds_missing_bar() -> None:
    # 1-minute bars with one missing minute.
    base = 1_704_105_300_000
    bars = _bars([base, base + 60_000, base + 180_000])
    report = detect_gaps(bars, timeframe=Timeframe.M1)
    assert report.missing_bars == 1
    assert report.gap_percentage > 0


def test_detect_gaps_no_gaps_in_continuous_series() -> None:
    base = 1_704_105_300_000
    bars = _bars([base + i * 60_000 for i in range(5)])
    report = detect_gaps(bars, timeframe=Timeframe.M1)
    assert report.missing_bars == 0
    assert report.gap_percentage == 0.0
