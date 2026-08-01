"""Canonical bar schema and timeframe arithmetic (ARCHITECTURE.md 2.3, 3.2).

Every bar written to Parquet has exactly these columns: ``ts`` (int64 UTC
epoch milliseconds, ascending, unique), ``open``, ``high``, ``low``, ``close``,
``volume`` (all float64). CSV imports may use any of the supported source
column names below; everything downstream only ever sees the canonical form.
"""

from __future__ import annotations

from app.domain.enums import Timeframe

REQUIRED_COLUMNS: tuple[str, ...] = ("timestamp", "open", "high", "low", "close", "volume")
NUMERIC_COLUMNS: tuple[str, ...] = ("open", "high", "low", "close", "volume")

CANONICAL_COLUMNS: tuple[str, ...] = ("ts", "open", "high", "low", "close", "volume")

# Expected spacing between consecutive bars for intraday gap detection.
TIMEFRAME_STEP_MS: dict[Timeframe, int] = {
    Timeframe.M1: 60_000,
    Timeframe.M3: 180_000,
    Timeframe.M5: 300_000,
    Timeframe.M10: 600_000,
    Timeframe.M15: 900_000,
    Timeframe.M30: 1_800_000,
    Timeframe.H1: 3_600_000,
    Timeframe.H2: 7_200_000,
    Timeframe.H4: 14_400_000,
    Timeframe.D1: 86_400_000,
    Timeframe.W1: 604_800_000,
}
