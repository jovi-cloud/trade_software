"""Structured explainability types for deterministic run observation.

Events are facts collected during execution. Human-readable ``message`` fields
are generated from templates — never from free-form strategy logging.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

EXPLAIN_SCHEMA_VERSION = 1


class ExplainLevel(StrEnum):
    """How much structured observation to collect during a run."""

    NONE = "none"
    TRADES_ONLY = "trades_only"
    FULL = "full"


class ExplainEventType(StrEnum):
    """Lifecycle and execution events recorded by :class:`ExplainCollector`."""

    RUN_STARTED = "run_started"
    DATASET_LOADED = "dataset_loaded"
    STRATEGY_LOADED = "strategy_loaded"
    PARAMETERS_APPLIED = "parameters_applied"
    BAR_PROCESSING_STARTED = "bar_processing_started"
    CONDITIONS_EVALUATED = "conditions_evaluated"
    SIGNAL_GENERATED = "signal_generated"
    ORDER_CREATED = "order_created"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    POSITION_OPENED = "position_opened"
    POSITION_UPDATED = "position_updated"
    POSITION_CLOSED = "position_closed"
    PROFIT_CALCULATED = "profit_calculated"
    METRICS_GENERATED = "metrics_generated"
    CHARTS_GENERATED = "charts_generated"
    RUN_COMPLETED = "run_completed"
    HUMAN_NARRATIVE = "human_narrative"


class ExplainLayer(StrEnum):
    """Log layer for UI filtering (Phase 5A foundation)."""

    SYSTEM = "system"
    EXECUTION = "execution"
    DECISION = "decision"
    NARRATIVE = "narrative"


class ExplainEventStatus(StrEnum):
    """Outcome status for a recorded event."""

    OK = "ok"
    REJECTED = "rejected"
    WARNING = "warning"
    INFO = "info"
    FAILED = "failed"


@dataclass(frozen=True)
class ExplainEvent:
    """One structured, reproducible observation from a backtest run."""

    seq: int
    event_type: ExplainEventType
    layer: ExplainLayer
    timestamp_ms: int
    bar_index: int | None
    reason_code: str
    status: ExplainEventStatus
    message: str
    schema_version: int = EXPLAIN_SCHEMA_VERSION
    event_id: str = ""
    order_id: int | None = None
    trade_id: int | None = None
    position_id: int | None = None
    instrument: str | None = None
    timeframe: str | None = None
    price: float | None = None
    quantity: float | None = None
    commission: float | None = None
    slippage: float | None = None
    cash: float | None = None
    portfolio_value: float | None = None
    pnl: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def trade_seq(self) -> int | None:
        """Backward-compatible alias for :attr:`trade_id`."""
        return self.trade_id
