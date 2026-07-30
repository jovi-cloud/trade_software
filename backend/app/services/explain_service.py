"""Query and reconstruct explainability data for persisted backtest runs."""

from __future__ import annotations

import json
from dataclasses import asdict

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.paths import DataPaths
from app.domain.explain import ExplainEvent
from app.engine.explain.bar_inspector import BarInspection, build_navigation, inspect_bar
from app.engine.explain.event_index import EventIndex
from app.engine.explain.serialize import events_from_json_list
from app.engine.explain.trade_inspector import TradeInspection, inspect_trade
from app.repositories.backtest_run_repo import BacktestRunRepository
from app.schemas.explain import (
    BarInspectionRead,
    ExplainEventFilter,
    ExplainEventRead,
    TradeInspectionRead,
)
from app.services.run_snapshot import RunSnapshotCache


class ExplainService:
    def __init__(self, session: Session, paths: DataPaths) -> None:
        self.session = session
        self.paths = paths
        self.repo = BacktestRunRepository(session)
        self._index_cache: dict[str, EventIndex] = {}
        self._snapshot_cache = RunSnapshotCache(session, paths)

    def list_events(
        self,
        run_id: str,
        *,
        filters: ExplainEventFilter,
        limit: int,
        offset: int,
        sort: str,
        order: str,
    ) -> tuple[list[ExplainEventRead], int]:
        index = self._load_index(run_id)
        filtered = _apply_filters(index.events, filters)
        sorted_events = _sort_events(filtered, sort=sort, order=order)
        page = sorted_events[offset : offset + limit]
        return [_event_to_read(event) for event in page], len(sorted_events)

    def get_trade(self, run_id: str, trade_id: int) -> TradeInspectionRead:
        index = self._load_index(run_id)
        inspection = inspect_trade(index, trade_id)
        if inspection is None:
            raise NotFoundError(f"Trade {trade_id} not found in run '{run_id}'")
        return _inspection_to_read(inspection)

    def list_trades(self, run_id: str) -> list[TradeInspectionRead]:
        index = self._load_index(run_id)
        return [_inspection_to_read(inspection) for inspection in _all_inspections(index)]

    def list_trade_events(
        self,
        run_id: str,
        trade_id: int,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[ExplainEventRead], int]:
        index = self._load_index(run_id)
        inspection = inspect_trade(index, trade_id)
        if inspection is None:
            raise NotFoundError(f"Trade {trade_id} not found in run '{run_id}'")
        events = tuple(index.by_seq[seq] for seq in inspection.event_seqs if seq in index.by_seq)
        page = events[offset : offset + limit]
        return [_event_to_read(event) for event in page], len(events)

    def get_bar(self, run_id: str, bar_index: int) -> BarInspectionRead:
        snapshot = self._snapshot_cache.get(run_id)
        if bar_index < 0 or bar_index >= snapshot.bar_count:
            raise ValidationError(
                f"bar_index must be between 0 and {snapshot.bar_count - 1} inclusive"
            )
        navigation = build_navigation(
            bar_index=bar_index,
            bar_count=snapshot.bar_count,
            index=snapshot.event_index,
        )
        inspection = inspect_bar(
            bar_index=bar_index,
            candles=snapshot.candles,
            orders=snapshot.orders,
            index=snapshot.event_index,
            navigation=navigation,
        )
        if inspection is None:
            raise NotFoundError(f"Bar {bar_index} not found in run '{run_id}'")
        bar_events = snapshot.event_index.by_bar_index.get(bar_index, ())
        return _bar_inspection_to_read(inspection, bar_events)

    def list_bar_events(
        self,
        run_id: str,
        bar_index: int,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[ExplainEventRead], int]:
        snapshot = self._snapshot_cache.get(run_id)
        if bar_index < 0 or bar_index >= snapshot.bar_count:
            raise ValidationError(
                f"bar_index must be between 0 and {snapshot.bar_count - 1} inclusive"
            )
        events = snapshot.event_index.by_bar_index.get(bar_index, ())
        filtered = tuple(event for event in events if event.layer.value != "narrative")
        page = filtered[offset : offset + limit]
        return [_event_to_read(event) for event in page], len(filtered)

    def _load_index(self, run_id: str) -> EventIndex:
        cached = self._index_cache.get(run_id)
        if cached is not None:
            return cached
        row = self.repo.get(run_id)
        if row is None:
            raise NotFoundError(f"Backtest run '{run_id}' not found")
        run = row[0]
        raw_items: list[dict[str, object]] = json.loads(run.explain_events_json)
        events = events_from_json_list(raw_items)
        index = EventIndex.build(events)
        self._index_cache[run_id] = index
        return index


def _apply_filters(
    events: tuple[ExplainEvent, ...], filters: ExplainEventFilter
) -> tuple[ExplainEvent, ...]:
    result = events
    if filters.layer is not None:
        result = tuple(event for event in result if event.layer is filters.layer)
    if filters.event_type is not None:
        result = tuple(event for event in result if event.event_type is filters.event_type)
    if filters.trade_id is not None:
        result = tuple(event for event in result if event.trade_id == filters.trade_id)
    if filters.order_id is not None:
        result = tuple(event for event in result if event.order_id == filters.order_id)
    if filters.position_id is not None:
        result = tuple(event for event in result if event.position_id == filters.position_id)
    if filters.reason_code is not None:
        result = tuple(event for event in result if event.reason_code == filters.reason_code)
    if filters.status is not None:
        result = tuple(event for event in result if event.status is filters.status)
    if filters.bar_index is not None:
        result = tuple(event for event in result if event.bar_index == filters.bar_index)
    if filters.timestamp_from_ms is not None:
        result = tuple(event for event in result if event.timestamp_ms >= filters.timestamp_from_ms)
    if filters.timestamp_to_ms is not None:
        result = tuple(event for event in result if event.timestamp_ms <= filters.timestamp_to_ms)
    if filters.q:
        needle = filters.q.lower()
        result = tuple(
            event
            for event in result
            if needle in event.message.lower() or needle in event.reason_code.lower()
        )
    return result


def _sort_events(
    events: tuple[ExplainEvent, ...], *, sort: str, order: str
) -> tuple[ExplainEvent, ...]:
    reverse = order == "desc"
    if sort == "timestamp_ms":
        return tuple(
            sorted(events, key=lambda item: (item.timestamp_ms, item.seq), reverse=reverse)
        )
    if sort == "bar_index":
        return tuple(
            sorted(
                events,
                key=lambda item: (item.bar_index if item.bar_index is not None else -1, item.seq),
                reverse=reverse,
            )
        )
    if sort == "event_type":
        return tuple(
            sorted(events, key=lambda item: (item.event_type.value, item.seq), reverse=reverse)
        )
    return tuple(sorted(events, key=lambda item: item.seq, reverse=reverse))


def _event_to_read(event: ExplainEvent) -> ExplainEventRead:
    payload = asdict(event)
    payload["trade_seq"] = event.trade_id
    return ExplainEventRead.model_validate(payload)


def _inspection_to_read(inspection: TradeInspection) -> TradeInspectionRead:
    return TradeInspectionRead.model_validate(
        {
            "summary": asdict(inspection.summary),
            "timeline": [asdict(step) for step in inspection.timeline],
            "event_seqs": list(inspection.event_seqs),
        }
    )


def _all_inspections(index: EventIndex) -> list[TradeInspection]:
    inspections: list[TradeInspection] = []
    for trade_id in index.trade_ids():
        inspection = inspect_trade(index, trade_id)
        if inspection is not None:
            inspections.append(inspection)
    return inspections


def _bar_inspection_to_read(
    inspection: BarInspection,
    bar_events: tuple[ExplainEvent, ...],
) -> BarInspectionRead:
    return BarInspectionRead.model_validate(
        {
            "bar_index": inspection.bar_index,
            "candle": {
                "bar_index": inspection.candle.bar_index,
                "ts": inspection.candle.ts,
                "open": inspection.candle.open,
                "high": inspection.candle.high,
                "low": inspection.candle.low,
                "close": inspection.candle.close,
                "volume": inspection.candle.volume,
            },
            "market_state": {
                "current_price": inspection.market_state.current_price,
                "open": inspection.market_state.open,
                "high": inspection.market_state.high,
                "low": inspection.market_state.low,
                "close": inspection.market_state.close,
                "volume": inspection.market_state.volume,
                "trend": inspection.market_state.trend,
                "volatility_pct": inspection.market_state.volatility_pct,
                "session": inspection.market_state.session,
                "indicators": inspection.market_state.indicators,
                "cash": inspection.market_state.cash,
                "portfolio_value": inspection.market_state.portfolio_value,
                "position": (
                    {
                        "side": inspection.market_state.position.side,
                        "quantity": inspection.market_state.position.quantity,
                        "entry_price": inspection.market_state.position.entry_price,
                    }
                    if inspection.market_state.position
                    else None
                ),
            },
            "conditions": [asdict(condition) for condition in inspection.conditions],
            "decision": {
                "decision_type": inspection.decision.decision_type.value,
                "reason_code": inspection.decision.reason_code,
                "message": inspection.decision.message,
                "related_event_seqs": list(inspection.decision.related_event_seqs),
            },
            "execution": {
                "occurred": inspection.execution.occurred,
                "message": inspection.execution.message,
                "order_ref": inspection.execution.order_ref,
                "fill_price": inspection.execution.fill_price,
                "quantity": inspection.execution.quantity,
                "commission": inspection.execution.commission,
                "slippage": inspection.execution.slippage,
                "position": (
                    {
                        "side": inspection.execution.position.side,
                        "quantity": inspection.execution.position.quantity,
                        "entry_price": inspection.execution.position.entry_price,
                    }
                    if inspection.execution.position
                    else None
                ),
                "pnl": inspection.execution.pnl,
            },
            "timeline": [asdict(step) for step in inspection.timeline],
            "open_orders": [asdict(order) for order in inspection.open_orders],
            "filled_orders": [asdict(order) for order in inspection.filled_orders],
            "cancelled_orders": [asdict(order) for order in inspection.cancelled_orders],
            "event_seqs": list(inspection.event_seqs),
            "navigation": asdict(inspection.navigation),
            "explain_events": [_event_to_read(event) for event in bar_events],
        }
    )
