"""Session-aware gap detection for imported bar data."""

from __future__ import annotations

from datetime import UTC, datetime
from itertools import pairwise
from typing import cast
from zoneinfo import ZoneInfo

import polars as pl

from app.core.logging import get_logger
from app.data.data_pipeline.metadata import MAX_SAMPLE_COUNT, SessionConfig
from app.data.data_pipeline.report import GapReport
from app.data.data_pipeline.session_bounds import resolve_session_bar_bounds
from app.domain.enums import Timeframe

logger = get_logger(__name__)

MAX_MISSING_DETAILS = 500


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour, minute = value.split(":")
    return int(hour), int(minute)


def _epoch_ms_to_local_iso(epoch_ms: int, tz: ZoneInfo) -> str:
    return datetime.fromtimestamp(epoch_ms / 1000, tz=UTC).astimezone(tz).isoformat()


def _resolve_step_ms(timeframe: Timeframe | None, dominant_ms: int | None) -> int | None:
    from app.data.data_pipeline.metadata import DETECTABLE_TIMEFRAMES_MS

    if timeframe is not None:
        return DETECTABLE_TIMEFRAMES_MS.get(timeframe)
    return dominant_ms


def _is_trading_day(day_key: str, config: SessionConfig, tz: ZoneInfo) -> bool:
    if day_key in config.holidays:
        return False
    day = datetime.strptime(day_key, "%Y-%m-%d").replace(tzinfo=tz)
    return day.weekday() in config.trading_days


def _minutes_of_day(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def _format_intraday_gap(
    day_key: str,
    *,
    range_start_ms: int,
    range_end_ms: int,
    missing_count: int,
    tz: ZoneInfo,
    timezone_label: str,
) -> str:
    start = datetime.fromtimestamp(range_start_ms / 1000, tz=UTC).astimezone(tz)
    end = datetime.fromtimestamp(range_end_ms / 1000, tz=UTC).astimezone(tz)
    return (
        f"{day_key}: {missing_count} missing bar(s) between "
        f"{start.strftime('%H:%M')} and {end.strftime('%H:%M')} ({timezone_label})"
    )


def _format_gap_sample(
    prev_ts: int,
    curr_ts: int,
    *,
    missing_count: int,
    tz: ZoneInfo,
) -> str:
    start = _epoch_ms_to_local_iso(prev_ts, tz)
    end = _epoch_ms_to_local_iso(curr_ts, tz)
    return f"{start} -> {end} ({missing_count} bar(s))"


def detect_gaps(
    bars: pl.DataFrame,
    *,
    timeframe: Timeframe | None = None,
    dominant_interval_ms: int | None = None,
    session: SessionConfig | None = None,
    large_jump_multiplier: float = 3.0,
) -> GapReport:
    """Detect missing bars inside trading sessions.

    Only gaps between consecutive bars on the *same* exchange-local trading day
    are counted. Overnight closes, weekends, holidays, and entire weekdays with
    no data are ignored.
    """
    session_config = session or SessionConfig()
    actual_bars = bars.height
    if actual_bars == 0:
        return GapReport(
            expected_bars=0,
            actual_bars=0,
            missing_bars=0,
            duplicate_bars=0,
            large_jumps=0,
            partial_trading_days=0,
            gap_percentage=0.0,
        )

    step_ms = _resolve_step_ms(timeframe, dominant_interval_ms)
    ts_list = sorted(cast(int, ts) for ts in bars.select("ts").to_series().to_list())
    duplicate_bars = actual_bars - len(set(ts_list))

    if not step_ms:
        return GapReport(
            expected_bars=actual_bars,
            actual_bars=actual_bars,
            missing_bars=0,
            duplicate_bars=duplicate_bars,
            large_jumps=0,
            partial_trading_days=0,
            gap_percentage=0.0,
        )

    tz = ZoneInfo(session_config.timezone)
    bounds = resolve_session_bar_bounds(session_config.open_time, session_config.close_time)
    session_minutes = bounds.last_bar_minutes - bounds.open_minutes
    expected_per_day = max(1, (session_minutes * 60_000) // step_ms + 1)

    missing_bars = 0
    large_jumps = 0
    missing_samples: list[str] = []
    jump_samples: list[str] = []
    missing_details: list[str] = []

    by_day: dict[str, int] = {}
    for ts in ts_list:
        local = datetime.fromtimestamp(ts / 1000, tz=UTC).astimezone(tz)
        day_key = local.strftime("%Y-%m-%d")
        by_day[day_key] = by_day.get(day_key, 0) + 1

    partial_days = sum(
        1
        for day_key, count in by_day.items()
        if _is_trading_day(day_key, session_config, tz) and count < expected_per_day * 0.5
    )

    for prev_ts, curr_ts in pairwise(ts_list):
        prev_local = datetime.fromtimestamp(prev_ts / 1000, tz=UTC).astimezone(tz)
        curr_local = datetime.fromtimestamp(curr_ts / 1000, tz=UTC).astimezone(tz)
        prev_day = prev_local.strftime("%Y-%m-%d")
        curr_day = curr_local.strftime("%Y-%m-%d")

        if prev_day != curr_day:
            continue
        if not _is_trading_day(prev_day, session_config, tz):
            continue

        prev_minutes = _minutes_of_day(prev_local)
        curr_minutes = _minutes_of_day(curr_local)
        if prev_minutes < bounds.open_minutes or curr_minutes > bounds.last_bar_minutes:
            continue

        diff = curr_ts - prev_ts
        if diff <= step_ms:
            continue

        gap_count = (diff // step_ms) - 1
        missing_bars += int(gap_count)
        gap_start_ms = prev_ts + step_ms
        gap_end_ms = curr_ts - step_ms
        detail = _format_intraday_gap(
            prev_day,
            range_start_ms=gap_start_ms,
            range_end_ms=gap_end_ms,
            missing_count=gap_count,
            tz=tz,
            timezone_label=session_config.timezone,
        )
        if len(missing_details) < MAX_MISSING_DETAILS:
            missing_details.append(detail)
        if len(missing_samples) < MAX_SAMPLE_COUNT:
            missing_samples.append(
                _format_gap_sample(prev_ts, curr_ts, missing_count=gap_count, tz=tz)
            )
        if diff > step_ms * large_jump_multiplier:
            large_jumps += 1
            if len(jump_samples) < MAX_SAMPLE_COUNT:
                jump_samples.append(
                    _format_gap_sample(prev_ts, curr_ts, missing_count=gap_count, tz=tz)
                )

    expected_bars = actual_bars + missing_bars
    gap_percentage = (missing_bars / expected_bars * 100.0) if expected_bars else 0.0

    if missing_bars > 0:
        logger.warning(
            "Intraday missing bars detected during import",
            extra={
                "missing_bars": missing_bars,
                "timezone": session_config.timezone,
                "session_open": session_config.open_time,
                "session_close": session_config.close_time,
                "sample_count": len(missing_samples),
                "details_logged": len(missing_details),
            },
        )
        for detail in missing_details[:10]:
            logger.warning("Missing bar detail: %s", detail)

    return GapReport(
        expected_bars=expected_bars,
        actual_bars=actual_bars,
        missing_bars=missing_bars,
        duplicate_bars=duplicate_bars,
        large_jumps=large_jumps,
        partial_trading_days=partial_days,
        gap_percentage=round(gap_percentage, 4),
        missing_timestamps=tuple(missing_samples),
        large_jump_samples=tuple(jump_samples),
        missing_details=tuple(missing_details),
    )
