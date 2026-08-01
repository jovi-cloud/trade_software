"""Pipeline configuration and column mapping (ARCHITECTURE.md 2.3)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.domain.enums import Timeframe

# Source column names after header normalisation. Aliases are matched case-insensitively.
TIMESTAMP_ALIASES: frozenset[str] = frozenset(
    {"timestamp", "datetime", "date_time", "date", "time", "ts"}
)
OPEN_ALIASES: frozenset[str] = frozenset({"open", "o", "open_price"})
HIGH_ALIASES: frozenset[str] = frozenset({"high", "h", "high_price"})
LOW_ALIASES: frozenset[str] = frozenset({"low", "l", "low_price"})
CLOSE_ALIASES: frozenset[str] = frozenset({"close", "c", "close_price", "adj_close"})
VOLUME_ALIASES: frozenset[str] = frozenset({"volume", "vol", "qty", "quantity"})

CANONICAL_SOURCE_COLUMNS: tuple[str, ...] = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
)

ALIAS_GROUPS: dict[str, frozenset[str]] = {
    "timestamp": TIMESTAMP_ALIASES,
    "open": OPEN_ALIASES,
    "high": HIGH_ALIASES,
    "low": LOW_ALIASES,
    "close": CLOSE_ALIASES,
    "volume": VOLUME_ALIASES,
}

DETECTABLE_TIMEFRAMES_MS: dict[Timeframe, int] = {
    Timeframe.M1: 60_000,
    Timeframe.M3: 180_000,
    Timeframe.M5: 300_000,
    Timeframe.M10: 600_000,
    Timeframe.M15: 900_000,
    Timeframe.M30: 1_800_000,
    Timeframe.H1: 3_600_000,
    Timeframe.D1: 86_400_000,
}

QUALITY_REJECT_THRESHOLD = 70
MAX_SAMPLE_COUNT = 20


@dataclass(frozen=True)
class SessionConfig:
    """Exchange session boundaries in local exchange time."""

    open_time: str = "09:15"
    close_time: str = "15:25"
    timezone: str = "UTC"
    # Monday=0 … Sunday=6
    trading_days: tuple[int, ...] = (0, 1, 2, 3, 4)
    holidays: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class SessionCleaningOptions:
    remove_outside_session: bool = False
    remove_weekend_bars: bool = False
    remove_holiday_bars: bool = False
    remove_days_with_spikes_over_10pct: bool = False
    remove_days_with_spikes_over_20pct: bool = False
    remove_intraday_spike_days_over_10pct: bool = False
    remove_intraday_spike_days_over_20pct: bool = False
    remove_cross_day_spike_days_over_10pct: bool = False
    remove_cross_day_spike_days_over_20pct: bool = False

    @property
    def enabled(self) -> bool:
        return (
            self.remove_outside_session
            or self.remove_weekend_bars
            or self.remove_holiday_bars
            or self.price_anomaly_cleaning_enabled
        )

    @property
    def price_anomaly_cleaning_enabled(self) -> bool:
        return (
            self.remove_days_with_spikes_over_10pct
            or self.remove_days_with_spikes_over_20pct
            or self.remove_intraday_spike_days_over_10pct
            or self.remove_intraday_spike_days_over_20pct
            or self.remove_cross_day_spike_days_over_10pct
            or self.remove_cross_day_spike_days_over_20pct
        )


@dataclass(frozen=True)
class PipelineConfig:
    """Full import configuration passed to the pipeline orchestrator."""

    timeframe: Timeframe | None = None
    column_mapping: Mapping[str, str] = field(default_factory=dict)
    session: SessionConfig = field(default_factory=SessionConfig)
    session_cleaning: SessionCleaningOptions = field(default_factory=SessionCleaningOptions)
    remove_duplicate_rows: bool = True
    instrument: str = ""
    exchange: str = ""
