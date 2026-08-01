"""Tests for exchange session validation."""

from __future__ import annotations

from datetime import UTC, datetime

import polars as pl

from app.data.data_pipeline.metadata import SessionConfig
from app.data.data_pipeline.session_validator import validate_session


def _ts(local: str, tz: str = "Asia/Kolkata") -> int:
    from zoneinfo import ZoneInfo

    dt = datetime.strptime(local, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz))
    return int(dt.astimezone(UTC).timestamp() * 1000)


def _bar(ts: int) -> dict[str, float | int]:
    return {"ts": ts, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000.0}


def test_validate_session_collects_missing_open_and_close_samples() -> None:
    config = SessionConfig(timezone="Asia/Kolkata", open_time="09:15", close_time="15:25")
    bars = pl.DataFrame(
        [
            _bar(_ts("2024-01-02 09:20")),  # Tuesday, no 09:15 open
            _bar(_ts("2024-01-02 15:20")),  # no 15:25 close
            _bar(_ts("2024-01-03 09:15")),
            _bar(_ts("2024-01-03 15:25")),
        ]
    )

    report = validate_session(bars, config)

    assert report.missing_opening_candles == 1
    assert report.missing_closing_candles == 1
    assert len(report.missing_opening_samples) == 1
    assert "2024-01-02" in report.missing_opening_samples[0]
    assert "09:15" in report.missing_opening_samples[0]
    assert len(report.missing_closing_samples) == 1
    assert "2024-01-02" in report.missing_closing_samples[0]
    assert "15:25" in report.missing_closing_samples[0]


def test_validate_session_collects_weekend_bar_samples() -> None:
    bars = pl.DataFrame(
        [
            _bar(_ts("2024-01-01 09:15")),  # Monday
            _bar(_ts("2024-01-06 09:15")),  # Saturday
            _bar(_ts("2024-01-07 10:00")),  # Sunday
        ]
    )

    report = validate_session(bars, SessionConfig(timezone="Asia/Kolkata"))

    assert report.unexpected_weekend_bars == 2
    assert len(report.unexpected_weekend_samples) == 2
    assert "2024-01-06" in report.unexpected_weekend_samples[0]
    assert "2024-01-07" in report.unexpected_weekend_samples[1]
