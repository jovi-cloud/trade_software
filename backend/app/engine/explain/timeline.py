"""Assemble a complete execution timeline from engine and service events."""

from __future__ import annotations

from dataclasses import replace

from app.domain.explain import ExplainEvent, ExplainEventType, ExplainLevel
from app.engine.explain.collector import ExplainCollector


def assemble_timeline(
    engine_events: tuple[ExplainEvent, ...],
    *,
    level: ExplainLevel,
    dataset_event: ExplainEvent | None,
    metrics_event: ExplainEvent | None,
    charts_event: ExplainEvent | None,
) -> tuple[ExplainEvent, ...]:
    """Insert service-layer events into the engine timeline and renumber."""
    if level is ExplainLevel.NONE:
        return ()

    ordered: list[ExplainEvent] = []
    run_completed: ExplainEvent | None = None

    for event in engine_events:
        if event.event_type is ExplainEventType.RUN_COMPLETED:
            run_completed = event
            continue
        ordered.append(event)
        if (
            event.event_type is ExplainEventType.RUN_STARTED
            and dataset_event is not None
        ):
            ordered.append(dataset_event)

    if metrics_event is not None:
        ordered.append(metrics_event)
    if charts_event is not None:
        ordered.append(charts_event)
    if run_completed is not None:
        ordered.append(run_completed)

    return tuple(replace(event, seq=index) for index, event in enumerate(ordered, start=1))


def service_collector(level: ExplainLevel, *, timestamp_ms: int = 0) -> ExplainCollector:
    collector = ExplainCollector(level)
    collector.set_clock(timestamp_ms)
    return collector
