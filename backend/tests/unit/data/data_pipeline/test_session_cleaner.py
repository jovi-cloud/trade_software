"""Tests for session-boundary bar removal."""

from __future__ import annotations

from datetime import UTC, datetime

import polars as pl

from app.data.data_pipeline.metadata import SessionCleaningOptions, SessionConfig
from app.data.data_pipeline.session_cleaner import clean_session_bars


def _ts(local: str, tz: str = "Asia/Kolkata") -> int:
    from zoneinfo import ZoneInfo

    dt = datetime.strptime(local, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(tz))
    return int(dt.astimezone(UTC).timestamp() * 1000)


def _bar(ts: int) -> dict[str, float | int]:
    return {"ts": ts, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000.0}


def test_clean_session_bars_removes_outside_session() -> None:
    config = SessionConfig(timezone="Asia/Kolkata", open_time="09:15", close_time="15:30")
    bars = pl.DataFrame(
        [
            _bar(_ts("2024-01-01 09:15")),
            _bar(_ts("2024-01-01 08:00")),
            _bar(_ts("2024-01-01 15:30")),
            _bar(_ts("2024-01-01 16:00")),
        ]
    )

    cleaned, report = clean_session_bars(
        bars,
        config,
        SessionCleaningOptions(remove_outside_session=True),
    )

    assert cleaned.height == 2
    assert any(action.action == "remove_outside_session_bars" for action in report.actions)
    assert report.actions[0].count == 2


def test_clean_session_bars_removes_weekend_rows() -> None:
    config = SessionConfig(timezone="Asia/Kolkata")
    bars = pl.DataFrame(
        [
            _bar(_ts("2024-01-01 09:15")),  # Monday
            _bar(_ts("2024-01-06 09:15")),  # Saturday
        ]
    )

    cleaned, report = clean_session_bars(
        bars,
        config,
        SessionCleaningOptions(remove_weekend_bars=True),
    )

    assert cleaned.height == 1
    assert report.actions[0].action == "remove_weekend_bars"
    assert report.actions[0].count == 1
