"""Exchange session validation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from zoneinfo import ZoneInfo

import polars as pl

from app.data.data_pipeline.metadata import MAX_SAMPLE_COUNT, SessionConfig
from app.data.data_pipeline.report import SessionReport


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour, minute = value.split(":")
    return int(hour), int(minute)


def validate_session(bars: pl.DataFrame, config: SessionConfig) -> SessionReport:
    """Detect session boundary violations in exchange-local time."""
    if bars.height == 0:
        return SessionReport()

    tz = ZoneInfo(config.timezone)
    open_h, open_m = _parse_hhmm(config.open_time)
    close_h, close_m = _parse_hhmm(config.close_time)
    open_minutes = open_h * 60 + open_m
    close_minutes = close_h * 60 + close_m
    trading_days = set(config.trading_days)
    holidays = config.holidays

    missing_open = 0
    missing_close = 0
    outside_session = 0
    weekend_bars = 0
    holiday_bars = 0
    outside_samples: list[str] = []

    ts_series = bars.select("ts").to_series().to_list()
    by_day: dict[str, list[tuple[int, int]]] = {}

    for ts in ts_series:
        dt = datetime.fromtimestamp(cast(int, ts) / 1000, tz=UTC).astimezone(tz)
        day_key = dt.strftime("%Y-%m-%d")
        minutes = dt.hour * 60 + dt.minute
        by_day.setdefault(day_key, []).append((cast(int, ts), minutes))

        if dt.weekday() not in trading_days:
            weekend_bars += 1
        if day_key in holidays:
            holiday_bars += 1
        if minutes < open_minutes or minutes > close_minutes:
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
        if not any(abs(m - open_minutes) <= 1 for m in minutes_list):
            missing_open += 1
        if not any(abs(m - close_minutes) <= 1 for m in minutes_list):
            missing_close += 1

    return SessionReport(
        missing_opening_candles=missing_open,
        missing_closing_candles=missing_close,
        candles_outside_session=outside_session,
        unexpected_weekend_bars=weekend_bars,
        unexpected_holiday_bars=holiday_bars,
        outside_session_samples=tuple(outside_samples),
    )
