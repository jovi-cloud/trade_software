"""Indexed lookups over explain events for fast filtering."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.explain import ExplainEvent, ExplainEventType, ExplainLayer


@dataclass(frozen=True)
class EventIndex:
    """Pre-built indexes for a run's explain events."""

    events: tuple[ExplainEvent, ...]
    by_seq: dict[int, ExplainEvent]
    by_trade_id: dict[int, tuple[ExplainEvent, ...]]
    by_order_id: dict[int, tuple[ExplainEvent, ...]]
    by_position_id: dict[int, tuple[ExplainEvent, ...]]
    by_layer: dict[ExplainLayer, tuple[ExplainEvent, ...]]
    by_event_type: dict[ExplainEventType, tuple[ExplainEvent, ...]]
    by_reason_code: dict[str, tuple[ExplainEvent, ...]]
    by_bar_index: dict[int, tuple[ExplainEvent, ...]]

    @classmethod
    def build(cls, events: tuple[ExplainEvent, ...]) -> EventIndex:
        by_seq = {event.seq: event for event in events}
        by_trade: dict[int, list[ExplainEvent]] = {}
        by_order: dict[int, list[ExplainEvent]] = {}
        by_position: dict[int, list[ExplainEvent]] = {}
        by_layer: dict[ExplainLayer, list[ExplainEvent]] = {}
        by_type: dict[ExplainEventType, list[ExplainEvent]] = {}
        by_reason: dict[str, list[ExplainEvent]] = {}
        by_bar: dict[int, list[ExplainEvent]] = {}

        for event in events:
            if event.trade_id is not None:
                by_trade.setdefault(event.trade_id, []).append(event)
            if event.order_id is not None:
                by_order.setdefault(event.order_id, []).append(event)
            if event.position_id is not None:
                by_position.setdefault(event.position_id, []).append(event)
            if event.bar_index is not None:
                by_bar.setdefault(event.bar_index, []).append(event)
            by_layer.setdefault(event.layer, []).append(event)
            by_type.setdefault(event.event_type, []).append(event)
            by_reason.setdefault(event.reason_code, []).append(event)

        return cls(
            events=events,
            by_seq=by_seq,
            by_trade_id={key: tuple(value) for key, value in by_trade.items()},
            by_order_id={key: tuple(value) for key, value in by_order.items()},
            by_position_id={key: tuple(value) for key, value in by_position.items()},
            by_layer={key: tuple(value) for key, value in by_layer.items()},
            by_event_type={key: tuple(value) for key, value in by_type.items()},
            by_reason_code={key: tuple(value) for key, value in by_reason.items()},
            by_bar_index={key: tuple(value) for key, value in by_bar.items()},
        )

    def trade_ids(self) -> tuple[int, ...]:
        return tuple(sorted(self.by_trade_id))

    def order_ids_for_trade(self, trade_id: int) -> tuple[int, ...]:
        order_ids: set[int] = set()
        for event in self.by_trade_id.get(trade_id, ()):
            if event.order_id is not None:
                order_ids.add(event.order_id)
        return tuple(sorted(order_ids))
