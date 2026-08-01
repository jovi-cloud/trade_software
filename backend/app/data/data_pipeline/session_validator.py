"""Exchange session validation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from zoneinfo import ZoneInfo

import polars as pl

from app.data.data_pipeline.metadata import MAX_SAMPLE_COUNT, SessionConfig
from app.data.data_pipeline.report import SessionReport
from app.data.data_pipeline.session_bounds import (
    matches_bar_time,
    resolve_session_bar_bounds,
)


def _expected_bar_iso(day_key: str, hhmm: str, tz: ZoneInfo) -> str:
    hour, minute = map(int, hhmm.split(":"))
    day = datetime.strptime(day_key, "%Y-%m-%d")
    return day.replace(hour=hour, minute=minute, tzinfo=tz).isoformat()


def validate_session(bars: pl.DataFrame, config: SessionConfig) -> SessionReport:
    """Detect session boundary violations in exchange-local time."""
    if bars.height == 0:
        return SessionReport()

    tz = ZoneInfo(config.timezone)
    bounds = resolve_session_bar_bounds(config.open_time, config.close_time)
    trading_days = set(config.trading_days)
    holidays = config.holidays

    missing_open = 0
    missing_close = 0
    outside_session = 0
    weekend_bars = 0
    holiday_bars = 0
    missing_open_samples: list[str] = []
    missing_close_samples: list[str] = []
    outside_samples: list[str] = []
    weekend_samples: list[str] = []
    holiday_samples: list[str] = []

    ts_series = bars.select("ts").to_series().to_list()
    by_day: dict[str, list[tuple[int, int]]] = {}

    for ts in ts_series:
        dt = datetime.fromtimestamp(cast(int, ts) / 1000, tz=UTC).astimezone(tz)
        day_key = dt.strftime("%Y-%m-%d")
        minutes = dt.hour * 60 + dt.minute
        by_day.setdefault(day_key, []).append((cast(int, ts), minutes))

        if dt.weekday() not in trading_days:
            weekend_bars += 1
            if len(weekend_samples) < MAX_SAMPLE_COUNT:
                weekend_samples.append(dt.isoformat())
        if day_key in holidays:
            holiday_bars += 1
            if len(holiday_samples) < MAX_SAMPLE_COUNT:
                holiday_samples.append(dt.isoformat())
        if minutes < bounds.open_minutes or minutes > bounds.last_bar_minutes:
            outside_session += 1
            if len(outside_samples) < MAX_SAMPLE_COUNT:
                outside_samples.append(dt.isoformat())

    for day_key, entries in by_day.items():
        if day_key in holidays:
            continue
        dt = datetime.strptime(day_key, "%Y-%m-%d").replace(tzinfo=tz)
        if dt.weekday() not in trading_days:
            continue
        minutes_list = [m for _, m in entries]
        if not any(matches_bar_time(m, bounds.open_minutes) for m in minutes_list):
            missing_open += 1
            if len(missing_open_samples) < MAX_SAMPLE_COUNT:
                missing_open_samples.append(_expected_bar_iso(day_key, config.open_time, tz))
        if not any(matches_bar_time(m, bounds.last_bar_minutes) for m in minutes_list):
            missing_close += 1
            if len(missing_close_samples) < MAX_SAMPLE_COUNT:
                missing_close_samples.append(_expected_bar_iso(day_key, config.close_time, tz))

    return SessionReport(
        missing_opening_candles=missing_open,
        missing_closing_candles=missing_close,
        candles_outside_session=outside_session,
        unexpected_weekend_bars=weekend_bars,
        unexpected_holiday_bars=holiday_bars,
        missing_opening_samples=tuple(missing_open_samples),
        missing_closing_samples=tuple(missing_close_samples),
        outside_session_samples=tuple(outside_samples),
        unexpected_weekend_samples=tuple(weekend_samples),
        unexpected_holiday_samples=tuple(holiday_samples),
    )
