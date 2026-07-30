"""Gap and duplicate bar detection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import polars as pl

from app.data.data_pipeline.metadata import DETECTABLE_TIMEFRAMES_MS, MAX_SAMPLE_COUNT
from app.data.data_pipeline.report import GapReport
from app.domain.enums import Timeframe


def _epoch_ms_to_iso(epoch_ms: int) -> str:
    return datetime.fromtimestamp(epoch_ms / 1000, tz=UTC).isoformat()


def _resolve_step_ms(timeframe: Timeframe | None, dominant_ms: int | None) -> int | None:
    if timeframe is not None:
        return DETECTABLE_TIMEFRAMES_MS.get(timeframe)
    return dominant_ms


def detect_gaps(
    bars: pl.DataFrame,
    *,
    timeframe: Timeframe | None = None,
    dominant_interval_ms: int | None = None,
    large_jump_multiplier: float = 3.0,
) -> GapReport:
    """Detect missing bars, duplicates, and large time jumps."""
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
    ts_list = bars.select("ts").to_series().to_list()
    duplicate_bars = actual_bars - len(set(ts_list))

    missing_bars = 0
    large_jumps = 0
    missing_samples: list[str] = []
    jump_samples: list[str] = []
    partial_days: set[str] = set()

    if step_ms and actual_bars > 1:
        for i in range(1, len(ts_list)):
            prev_ts = cast(int, ts_list[i - 1])
            curr_ts = cast(int, ts_list[i])
            diff = curr_ts - prev_ts
            if diff == step_ms:
                continue
            if diff > step_ms:
                gaps_in_interval = (diff // step_ms) - 1
                missing_bars += int(gaps_in_interval)
                if len(missing_samples) < MAX_SAMPLE_COUNT:
                    prev_iso = _epoch_ms_to_iso(prev_ts)
                    curr_iso = _epoch_ms_to_iso(curr_ts)
                    missing_samples.append(f"{prev_iso} -> {curr_iso}")
                if diff > step_ms * large_jump_multiplier:
                    large_jumps += 1
                    if len(jump_samples) < MAX_SAMPLE_COUNT:
                        prev_iso = _epoch_ms_to_iso(prev_ts)
                        curr_iso = _epoch_ms_to_iso(curr_ts)
                        jump_samples.append(f"{prev_iso} -> {curr_iso}")

        # Partial trading days: days with fewer bars than a naive full session estimate.
        by_day: dict[str, int] = {}
        for ts in ts_list:
            day = datetime.fromtimestamp(cast(int, ts) / 1000, tz=UTC).strftime("%Y-%m-%d")
            by_day[day] = by_day.get(day, 0) + 1
        if step_ms:
            # Rough session estimate: 6h15m for NSE-style sessions.
            session_minutes = 375
            expected_per_day = max(1, (session_minutes * 60_000) // step_ms)
            for day, count in by_day.items():
                if count < expected_per_day * 0.5:
                    partial_days.add(day)

    expected_bars = actual_bars + missing_bars
    gap_percentage = (missing_bars / expected_bars * 100.0) if expected_bars else 0.0

    return GapReport(
        expected_bars=expected_bars,
        actual_bars=actual_bars,
        missing_bars=missing_bars,
        duplicate_bars=duplicate_bars,
        large_jumps=large_jumps,
        partial_trading_days=len(partial_days),
        gap_percentage=round(gap_percentage, 4),
        missing_timestamps=tuple(missing_samples),
        large_jump_samples=tuple(jump_samples),
    )
