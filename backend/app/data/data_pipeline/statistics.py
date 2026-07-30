"""Timeframe detection and dataset statistics."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import cast

import polars as pl

from app.data.data_pipeline.metadata import DETECTABLE_TIMEFRAMES_MS
from app.data.data_pipeline.report import DatasetStatistics, TimeframeReport
from app.domain.enums import Timeframe


def _nearest_timeframe(interval_ms: int) -> Timeframe | None:
    best: Timeframe | None = None
    best_delta = float("inf")
    for tf, step in DETECTABLE_TIMEFRAMES_MS.items():
        delta = abs(interval_ms - step)
        if delta < best_delta:
            best_delta = delta
            best = tf
    # Reject if more than 10% off the nearest canonical interval.
    if best is not None and best_delta > DETECTABLE_TIMEFRAMES_MS[best] * 0.1:
        return None
    return best


def detect_timeframe(bars: pl.DataFrame) -> TimeframeReport:
    """Detect the dominant bar interval and flag inconsistent spacing."""
    if bars.height < 2:
        return TimeframeReport(detected=None, is_consistent=True)

    diffs = (
        bars.select(pl.col("ts").diff().alias("diff"))
        .filter(pl.col("diff").is_not_null() & (pl.col("diff") > 0))
        .select("diff")
        .to_series()
        .to_list()
    )
    if not diffs:
        return TimeframeReport(detected=None, is_consistent=False)

    counter = Counter(cast(int, d) for d in diffs)
    dominant_ms, _ = counter.most_common(1)[0]
    detected = _nearest_timeframe(dominant_ms)
    tolerance = dominant_ms * 0.1
    inconsistent = sum(1 for d in diffs if abs(cast(int, d) - dominant_ms) > tolerance)
    total = len(diffs)
    is_consistent = (inconsistent / total) <= 0.05 if total else True

    return TimeframeReport(
        detected=detected,
        is_consistent=is_consistent,
        dominant_interval_ms=dominant_ms,
        inconsistent_intervals=inconsistent,
    )


def compute_statistics(
    bars: pl.DataFrame,
    *,
    instrument: str,
    timeframe: str | None,
    missing_bars: int,
    duplicate_bars: int,
    gap_percentage: float,
    quality_score: int,
) -> DatasetStatistics:
    """Compute summary statistics for a validated dataset."""
    total_bars = bars.height
    if total_bars == 0:
        return DatasetStatistics(
            date_range_start=None,
            date_range_end=None,
            total_bars=0,
            trading_days=0,
            average_daily_bars=0.0,
            min_price=None,
            max_price=None,
            average_volume=None,
            timeframe=timeframe,
            instrument=instrument,
            missing_bars=missing_bars,
            duplicate_bars=duplicate_bars,
            gap_percentage=gap_percentage,
            quality_score=quality_score,
        )

    ts_series = bars.select("ts").to_series()
    min_ts = cast(int, ts_series.min())
    max_ts = cast(int, ts_series.max())
    start = datetime.fromtimestamp(min_ts / 1000, tz=UTC)
    end = datetime.fromtimestamp(max_ts / 1000, tz=UTC)

    days = {
        datetime.fromtimestamp(cast(int, ts) / 1000, tz=UTC).strftime("%Y-%m-%d")
        for ts in ts_series.to_list()
    }
    trading_days = len(days)
    avg_daily = total_bars / trading_days if trading_days else 0.0

    price_min = cast(float, bars["low"].min())
    price_max = cast(float, bars["high"].max())
    avg_volume = cast(float, bars["volume"].mean())

    return DatasetStatistics(
        date_range_start=start,
        date_range_end=end,
        total_bars=total_bars,
        trading_days=trading_days,
        average_daily_bars=round(avg_daily, 2),
        min_price=price_min,
        max_price=price_max,
        average_volume=round(avg_volume, 2) if avg_volume is not None else None,
        timeframe=timeframe,
        instrument=instrument,
        missing_bars=missing_bars,
        duplicate_bars=duplicate_bars,
        gap_percentage=gap_percentage,
        quality_score=quality_score,
    )
