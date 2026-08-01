"""Tests for session-aware gap detection."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import polars as pl

from app.data.data_pipeline.gap_detector import detect_gaps
from app.data.data_pipeline.metadata import SessionConfig
from app.domain.enums import Timeframe

IST = ZoneInfo("Asia/Kolkata")
SESSION = SessionConfig(
    open_time="09:15",
    close_time="15:30",
    timezone="Asia/Kolkata",
)


def _ts(year: int, month: int, day: int, hour: int, minute: int) -> int:
    moment = datetime(year, month, day, hour, minute, tzinfo=IST)
    return int(moment.timestamp() * 1000)


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


def _full_session(day: tuple[int, int, int]) -> list[int]:
    year, month, day_num = day
    start = _ts(year, month, day_num, 9, 15)
    return [start + i * 60_000 for i in range(376)]


def test_detect_gaps_finds_intraday_missing_bar() -> None:
    base = _ts(2024, 1, 1, 9, 15)
    bars = _bars([base, base + 60_000, base + 180_000])
    report = detect_gaps(bars, timeframe=Timeframe.M1, session=SESSION)
    assert report.missing_bars == 1
    assert report.gap_percentage > 0
    assert len(report.missing_details) == 1
    assert "09:17" in report.missing_details[0]


def test_detect_gaps_no_gaps_in_continuous_session() -> None:
    bars = _bars(_full_session((2024, 1, 1)))
    report = detect_gaps(bars, timeframe=Timeframe.M1, session=SESSION)
    assert report.missing_bars == 0
    assert report.gap_percentage == 0.0


def test_overnight_gap_is_not_counted_as_missing() -> None:
    # Monday close to Tuesday open with no bars overnight.
    monday_close = _ts(2024, 1, 1, 15, 30)
    tuesday_open = _ts(2024, 1, 2, 9, 15)
    bars = _bars([monday_close, tuesday_open])
    report = detect_gaps(bars, timeframe=Timeframe.M1, session=SESSION)
    assert report.missing_bars == 0


def test_weekend_gap_is_not_counted_as_missing() -> None:
    friday_close = _ts(2024, 1, 5, 15, 30)
    monday_open = _ts(2024, 1, 8, 9, 15)
    bars = _bars([friday_close, monday_open])
    report = detect_gaps(bars, timeframe=Timeframe.M1, session=SESSION)
    assert report.missing_bars == 0


def test_full_missing_weekday_is_not_counted() -> None:
    monday = _full_session((2024, 1, 1))
    wednesday = _full_session((2024, 1, 3))
    bars = _bars(monday + wednesday)
    report = detect_gaps(bars, timeframe=Timeframe.M1, session=SESSION)
    assert report.missing_bars == 0


def test_missing_details_include_exchange_timezone() -> None:
    base = _ts(2024, 1, 1, 10, 0)
    bars = _bars([base, base + 180_000])
    report = detect_gaps(bars, timeframe=Timeframe.M1, session=SESSION)
    assert report.missing_bars == 2
    assert any("Asia/Kolkata" in detail for detail in report.missing_details)
