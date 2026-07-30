"""Serialize and normalize explain events for storage and API responses."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.domain.explain import (
    EXPLAIN_SCHEMA_VERSION,
    ExplainEvent,
    ExplainEventStatus,
    ExplainEventType,
    ExplainLayer,
)
from app.domain.reason_codes import normalize_reason_code


def event_to_dict(event: ExplainEvent) -> dict[str, Any]:
    """Convert an event to a JSON-safe dict with both trade_id and trade_seq."""
    payload = asdict(event)
    payload["trade_seq"] = event.trade_id
    if not payload.get("event_id"):
        payload["event_id"] = _default_event_id(event.seq)
    return payload


def event_from_dict(raw: dict[str, Any]) -> ExplainEvent:
    """Parse a stored event dict, filling defaults for legacy records."""
    schema_version = int(raw.get("schema_version", 0))
    seq = int(raw["seq"])
    trade_id = raw.get("trade_id")
    if trade_id is None and raw.get("trade_seq") is not None:
        trade_id = raw.get("trade_seq")

    metadata = raw.get("metadata")
    if metadata is None or not isinstance(metadata, dict):
        metadata = {}

    reason_code = normalize_reason_code(str(raw.get("reason_code", "")))

    return ExplainEvent(
        seq=seq,
        event_type=ExplainEventType(raw["event_type"]),
        layer=ExplainLayer(raw["layer"]),
        timestamp_ms=int(raw["timestamp_ms"]),
        bar_index=raw.get("bar_index"),
        reason_code=reason_code,
        status=ExplainEventStatus(raw["status"]),
        message=str(raw.get("message", "")),
        schema_version=schema_version if schema_version > 0 else EXPLAIN_SCHEMA_VERSION,
        event_id=str(raw.get("event_id") or _default_event_id(seq)),
        order_id=raw.get("order_id"),
        trade_id=trade_id,
        position_id=raw.get("position_id"),
        instrument=raw.get("instrument"),
        timeframe=raw.get("timeframe"),
        price=_optional_float(raw.get("price")),
        quantity=_optional_float(raw.get("quantity")),
        commission=_optional_float(raw.get("commission")),
        slippage=_optional_float(raw.get("slippage")),
        cash=_optional_float(raw.get("cash")),
        portfolio_value=_optional_float(raw.get("portfolio_value")),
        pnl=_optional_float(raw.get("pnl")),
        metadata=metadata,
    )


def events_from_json_list(items: list[dict[str, Any]]) -> tuple[ExplainEvent, ...]:
    return tuple(event_from_dict(item) for item in items)


def _default_event_id(seq: int) -> str:
    return f"evt-{seq:06d}"


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
