"""Domain enumerations.

Stdlib-only, per ARCHITECTURE.md 2.1 - the domain layer imports nothing else.
"""

from __future__ import annotations

from enum import StrEnum


class StrategyStatus(StrEnum):
    """Where an idea sits in the research loop (ARCHITECTURE.md 3.2)."""

    DRAFT = "draft"
    TESTING = "testing"
    VALIDATED = "validated"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class Timeframe(StrEnum):
    """Canonical timeframe strings (ARCHITECTURE.md 8)."""

    M1 = "1m"
    M3 = "3m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H2 = "2h"
    H4 = "4h"
    D1 = "1d"
    W1 = "1w"


class MarketType(StrEnum):
    """Asset class a strategy targets (mirrors instruments.asset_class, ARCHITECTURE.md 3.2)."""

    EQUITY = "equity"
    FUTURES = "futures"
    OPTIONS = "options"
    FX = "fx"
    CRYPTO = "crypto"
    INDEX = "index"


class Priority(StrEnum):
    """How urgently a strategy idea deserves research attention."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ImportStatus(StrEnum):
    """Lifecycle of a dataset's CSV import (ARCHITECTURE.md 2.3)."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class OrderType(StrEnum):
    """Market order types supported in engine v1."""

    BUY_MARKET = "buy_market"
    SELL_MARKET = "sell_market"
    CLOSE = "close"


class OrderStatus(StrEnum):
    """Lifecycle of a submitted order."""

    PENDING = "pending"
    FILLED = "filled"
    REJECTED = "rejected"


class PositionSide(StrEnum):
    """Direction of an open position."""

    LONG = "long"
    SHORT = "short"


class BacktestRunStatus(StrEnum):
    """Terminal state of a persisted backtest run."""

    COMPLETED = "completed"
    FAILED = "failed"
