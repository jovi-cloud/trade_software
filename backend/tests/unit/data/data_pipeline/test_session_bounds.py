"""Tests for session bar boundary resolution."""

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


def test_validate_session_treats_close_time_as_last_bar_open_for_5m() -> None:
    config = SessionConfig(timezone="Asia/Kolkata", open_time="09:15", close_time="15:25")
    bars = pl.DataFrame(
        [
            _bar(_ts("2024-01-01 09:15")),
            _bar(_ts("2024-01-01 15:25")),
        ]
    )

    report = validate_session(bars, config)

    assert report.missing_closing_candles == 0
    assert report.candles_outside_session == 0


def test_validate_session_flags_bar_after_last_5m_candle() -> None:
    config = SessionConfig(timezone="Asia/Kolkata", open_time="09:15", close_time="15:25")
    bars = pl.DataFrame(
        [
            _bar(_ts("2024-01-01 09:15")),
            _bar(_ts("2024-01-01 15:25")),
            _bar(_ts("2024-01-01 15:30")),
        ]
    )

    report = validate_session(bars, config)

    assert report.missing_closing_candles == 0
    assert report.candles_outside_session == 1
