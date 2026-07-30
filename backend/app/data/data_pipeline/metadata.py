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
    close_time: str = "15:30"
    timezone: str = "UTC"
    # Monday=0 … Sunday=6
    trading_days: tuple[int, ...] = (0, 1, 2, 3, 4)
    holidays: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class PipelineConfig:
    """Full import configuration passed to the pipeline orchestrator."""

    timeframe: Timeframe | None = None
    column_mapping: Mapping[str, str] = field(default_factory=dict)
    session: SessionConfig = field(default_factory=SessionConfig)
    remove_duplicate_rows: bool = True
    instrument: str = ""
    exchange: str = ""
