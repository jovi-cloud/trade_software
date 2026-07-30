"""Stable reason-code namespace for explainability events.

See ``docs/reason-codes.md`` for the full catalogue.
"""

from __future__ import annotations


class ReasonCode:
    """Reason-code constants — never use arbitrary strings in collectors."""

    # Signal
    SIGNAL_LONG = "signal.long"
    SIGNAL_SHORT = "signal.short"
    SIGNAL_EXIT = "signal.exit"
    SIGNAL_REJECTED = "signal.rejected"

    # Order
    ORDER_CREATED = "order.created"
    ORDER_SUBMITTED = "order.submitted"
    ORDER_FILLED = "order.filled"
    ORDER_CANCELLED = "order.cancelled"
    ORDER_REJECTED = "order.rejected"

    # Position
    POSITION_OPENED = "position.opened"
    POSITION_UPDATED = "position.updated"
    POSITION_CLOSED = "position.closed"

    # Risk
    RISK_INSUFFICIENT_CASH = "risk.insufficient_cash"
    RISK_MAX_POSITION = "risk.max_position"
    RISK_VALIDATION_FAILED = "risk.validation_failed"

    # System
    SYSTEM_RUN_STARTED = "system.run_started"
    SYSTEM_DATASET_LOADED = "system.dataset_loaded"
    SYSTEM_STRATEGY_LOADED = "system.strategy_loaded"
    SYSTEM_STRATEGY_LOAD_FAILED = "system.strategy_load_failed"
    SYSTEM_PARAMETERS_LOADED = "system.parameters_loaded"
    SYSTEM_BAR_PROCESSING = "system.bar_processing"
    DECISION_CONDITIONS_EVALUATED = "decision.conditions_evaluated"
    DECISION_NO_TRADE = "decision.no_trade"
    SYSTEM_METRICS_GENERATED = "system.metrics_generated"
    SYSTEM_CHARTS_GENERATED = "system.charts_generated"
    SYSTEM_COMPLETED = "system.completed"
    SYSTEM_PROFIT_CALCULATED = "system.profit_calculated"


_LEGACY_REASON_MAP: dict[str, str] = {
    "lifecycle.run_started": ReasonCode.SYSTEM_RUN_STARTED,
    "lifecycle.dataset_loaded": ReasonCode.SYSTEM_DATASET_LOADED,
    "lifecycle.strategy_loaded": ReasonCode.SYSTEM_STRATEGY_LOADED,
    "lifecycle.strategy_load_failed": ReasonCode.SYSTEM_STRATEGY_LOAD_FAILED,
    "lifecycle.metrics_generated": ReasonCode.SYSTEM_METRICS_GENERATED,
    "lifecycle.charts_generated": ReasonCode.SYSTEM_CHARTS_GENERATED,
    "lifecycle.run_completed": ReasonCode.SYSTEM_COMPLETED,
    "config.parameters_applied": ReasonCode.SYSTEM_PARAMETERS_LOADED,
    "execution.bar_processing": ReasonCode.SYSTEM_BAR_PROCESSING,
    "order.rejected": ReasonCode.ORDER_REJECTED,
}


def normalize_reason_code(code: str) -> str:
    """Map legacy reason codes to the Phase 5B namespace."""
    if code in _LEGACY_REASON_MAP:
        return _LEGACY_REASON_MAP[code]
    if code.startswith("strategy.signal."):
        action = code.rsplit(".", maxsplit=1)[-1].lower()
        if action in {"buy", "long"}:
            return ReasonCode.SIGNAL_LONG
        if action in {"sell short", "sell_short", "short"}:
            return ReasonCode.SIGNAL_SHORT
        if action in {"close", "exit"}:
            return ReasonCode.SIGNAL_EXIT
        return ReasonCode.SIGNAL_REJECTED
    if code.startswith("order.submitted."):
        return ReasonCode.ORDER_SUBMITTED
    if code.startswith("order.filled."):
        return ReasonCode.ORDER_FILLED
    if code.startswith("position.opened."):
        return ReasonCode.POSITION_OPENED
    if code.startswith("position.closed."):
        return ReasonCode.POSITION_CLOSED
    return code


def rejection_reason_code(reason: str) -> str:
    """Map a fill-time rejection message to a risk reason code."""
    lowered = reason.lower()
    if "insufficient cash" in lowered:
        return ReasonCode.RISK_INSUFFICIENT_CASH
    if "position already open" in lowered or "no open position" in lowered:
        return ReasonCode.RISK_MAX_POSITION
    return ReasonCode.ORDER_REJECTED
