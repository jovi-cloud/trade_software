"""Timeline assembly tests."""

from __future__ import annotations

from app.domain.explain import (
    ExplainEvent,
    ExplainEventStatus,
    ExplainEventType,
    ExplainLayer,
    ExplainLevel,
)
from app.engine.explain.timeline import assemble_timeline


def _event(
    seq: int,
    event_type: ExplainEventType,
    message: str = "test",
) -> ExplainEvent:
    return ExplainEvent(
        seq=seq,
        event_type=event_type,
        layer=ExplainLayer.SYSTEM,
        timestamp_ms=0,
        bar_index=None,
        reason_code="test",
        status=ExplainEventStatus.OK,
        order_id=None,
        trade_id=None,
        message=message,
    )


def test_assemble_timeline_inserts_service_events() -> None:
    engine_events = (
        _event(1, ExplainEventType.RUN_STARTED, "started"),
        _event(2, ExplainEventType.STRATEGY_LOADED, "loaded"),
        _event(3, ExplainEventType.RUN_COMPLETED, "done"),
    )
    dataset = _event(99, ExplainEventType.DATASET_LOADED, "dataset")
    metrics = _event(100, ExplainEventType.METRICS_GENERATED, "metrics")
    charts = _event(101, ExplainEventType.CHARTS_GENERATED, "charts")

    merged = assemble_timeline(
        engine_events,
        level=ExplainLevel.TRADES_ONLY,
        dataset_event=dataset,
        metrics_event=metrics,
        charts_event=charts,
    )

    assert [event.event_type for event in merged] == [
        ExplainEventType.RUN_STARTED,
        ExplainEventType.DATASET_LOADED,
        ExplainEventType.STRATEGY_LOADED,
        ExplainEventType.METRICS_GENERATED,
        ExplainEventType.CHARTS_GENERATED,
        ExplainEventType.RUN_COMPLETED,
    ]
    assert [event.seq for event in merged] == [1, 2, 3, 4, 5, 6]


def test_assemble_timeline_returns_empty_for_none_level() -> None:
    assert (
        assemble_timeline(
            (),
            level=ExplainLevel.NONE,
            dataset_event=None,
            metrics_event=None,
            charts_event=None,
        )
        == ()
    )
