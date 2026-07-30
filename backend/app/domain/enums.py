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
    M10 = "10m"
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


class StrategyCategory(StrEnum):
    """How a library strategy extracts edge. Drives Strategy Library grouping."""

    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    VOLUME = "volume"


class RiskLevel(StrEnum):
    """Declared aggressiveness of a strategy, for library filtering."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ParamType(StrEnum):
    """Parameter types the auto-generated parameter editor knows how to render.

    ``PERCENTAGE`` follows the project-wide convention (2.5 means 2.5%, not
    0.025). ``TIME`` is a zero-padded 24-hour ``HH:MM`` string. ``PRICE`` is a
    float in the instrument's quote currency.
    """

    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    CHOICE = "choice"
    STRING = "string"
    TIME = "time"
    PERCENTAGE = "percentage"
    PRICE = "price"


class ValidationRuleKind(StrEnum):
    """Declarative parameter constraints beyond min/max/step.

    A closed set rather than arbitrary predicates: rules must survive being
    serialised to the API and rendered as help text in the parameter editor.
    """

    LESS_THAN_PARAM = "less_than_param"
    GREATER_THAN_PARAM = "greater_than_param"
    NOT_EQUAL_PARAM = "not_equal_param"
    MULTIPLE_OF = "multiple_of"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"


class ValidationSeverity(StrEnum):
    """Whether a validation finding blocks execution or only warns."""

    ERROR = "error"
    WARNING = "warning"


class ImportStatus(StrEnum):
    """Lifecycle of a dataset's CSV import (ARCHITECTURE.md 2.3)."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DatasetStatus(StrEnum):
    """Import/validation state of a dataset aggregate (current version drives the state)."""

    UPLOADED = "uploaded"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    FAILED = "failed"


class DatasetLifecycle(StrEnum):
    """Whether a dataset is selectable, archived, or removed."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class DatasetVersionStatus(StrEnum):
    """Lifecycle of one immutable dataset version."""

    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
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
