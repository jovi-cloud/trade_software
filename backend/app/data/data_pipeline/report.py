"""Structured reports produced by the market data pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.enums import Timeframe


@dataclass(frozen=True)
class CleaningAction:
    action: str
    count: int
    detail: str = ""


@dataclass(frozen=True)
class CleaningReport:
    actions: tuple[CleaningAction, ...] = field(default_factory=tuple)

    @property
    def total_actions(self) -> int:
        return sum(action.count for action in self.actions)


@dataclass(frozen=True)
class ValidationReport:
    total_rows: int
    valid_rows: int
    invalid_dates: int
    invalid_prices: int
    duplicate_timestamps: int
    missing_timestamps: int
    out_of_order_timestamps: int = 0
    ohlc_violations: int = 0
    negative_volumes: int = 0
    non_positive_prices: int = 0
    nan_values: int = 0
    infinity_values: int = 0
    start_date: datetime | None = None
    end_date: datetime | None = None
    duplicate_samples: tuple[str, ...] = field(default_factory=tuple)
    gap_samples: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SessionReport:
    missing_opening_candles: int = 0
    missing_closing_candles: int = 0
    candles_outside_session: int = 0
    unexpected_weekend_bars: int = 0
    unexpected_holiday_bars: int = 0
    outside_session_samples: tuple[str, ...] = field(default_factory=tuple)

    @property
    def total_issues(self) -> int:
        return (
            self.missing_opening_candles
            + self.missing_closing_candles
            + self.candles_outside_session
            + self.unexpected_weekend_bars
            + self.unexpected_holiday_bars
        )


@dataclass(frozen=True)
class GapReport:
    expected_bars: int
    actual_bars: int
    missing_bars: int
    duplicate_bars: int
    large_jumps: int
    partial_trading_days: int
    gap_percentage: float
    missing_timestamps: tuple[str, ...] = field(default_factory=tuple)
    large_jump_samples: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TimeframeReport:
    detected: Timeframe | None
    is_consistent: bool
    dominant_interval_ms: int | None = None
    inconsistent_intervals: int = 0


@dataclass(frozen=True)
class DatasetStatistics:
    date_range_start: datetime | None
    date_range_end: datetime | None
    total_bars: int
    trading_days: int
    average_daily_bars: float
    min_price: float | None
    max_price: float | None
    average_volume: float | None
    timeframe: str | None
    instrument: str
    missing_bars: int
    duplicate_bars: int
    gap_percentage: float
    quality_score: int


@dataclass(frozen=True)
class PipelineReport:
    validation: ValidationReport
    cleaning: CleaningReport
    session: SessionReport
    gaps: GapReport
    timeframe: TimeframeReport
    statistics: DatasetStatistics
    quality_score: int
    rejected: bool
    rejection_reason: str | None = None
