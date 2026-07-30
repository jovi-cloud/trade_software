"""Query and reconstruct explainability data for persisted backtest runs."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.core.paths import DataPaths
from app.data import decision_store
from app.domain.decisions import BAR_INDEX_COLUMN, TIMESTAMP_COLUMN, DecisionSchema
from app.domain.explain import ExplainEvent
from app.engine.explain.bar_inspector import BarInspection, build_navigation, inspect_bar
from app.engine.explain.event_index import EventIndex
from app.engine.explain.serialize import events_from_json_list
from app.engine.explain.trade_inspector import TradeInspection, inspect_trade
from app.repositories.backtest_run_repo import BacktestRunRepository
from app.schemas.explain import (
    BarInspectionRead,
    ConditionSummaryRead,
    ConditionTraceRead,
    DecisionLogRead,
    DecisionRowRead,
    DecisionSchemaRead,
    DecisionSummaryRead,
    ExplainEventFilter,
    ExplainEventRead,
    OperandRead,
    TradeInspectionRead,
)
from app.services.run_snapshot import RunSnapshotCache

#: Largest decision-log window one request may return. The log itself is
#: uncapped; this bounds the *response*, which is a different concern - a client
#: paging a 194,553-bar log wants a screenful at a time, not 6 MB of JSON.
MAX_DECISION_WINDOW = 500


class ExplainService:
    def __init__(self, session: Session, paths: DataPaths) -> None:
        self.session = session
        self.paths = paths
        self.repo = BacktestRunRepository(session)
        self._index_cache: dict[str, EventIndex] = {}
        self._schema_cache: dict[str, DecisionSchema] = {}
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
        # The decision log is authoritative for per-bar facts when there is one:
        # a FULL run no longer duplicates its conditions into the JSON events, so
        # for those runs this is the only place the verdicts exist.
        decision_schema = self._decision_schema(run_id)
        row = decision_store.read_bar(self._decisions_path(run_id), bar_index)
        # Left as None when there is no log, so the inspector keeps deriving
        # conditions from the JSON events - which is how pre-log runs still read.
        conditions: list[ConditionTraceRead] | None = None
        operands: list[OperandRead] = []
        indicators: dict[str, float | str] = dict(inspection.market_state.indicators)
        if row is not None and decision_schema is not None:
            logged_indicators, logged_conditions, logged_operands = decision_store.split_columns(
                row
            )
            indicators = {**indicators, **logged_indicators}
            conditions = _conditions_from_log(logged_conditions, decision_schema)
            operands = _operands_from_log(logged_operands, decision_schema)
        return _bar_inspection_to_read(
            inspection,
            bar_events,
            conditions=conditions,
            indicators=indicators,
            operands=operands,
        )

    def get_decisions(self, run_id: str, *, start: int, count: int) -> DecisionLogRead:
        """One window of the per-bar decision log, in bar order."""
        if start < 0:
            raise ValidationError("start must not be negative")
        if count < 1 or count > MAX_DECISION_WINDOW:
            raise ValidationError(f"count must be between 1 and {MAX_DECISION_WINDOW} inclusive")
        schema = self._decision_schema(run_id)
        path = self._decisions_path(run_id)
        if schema is None or not decision_store.log_exists(path):
            raise NotFoundError(
                f"Run '{run_id}' has no decision log. Re-run it with full "
                "explainability to record one."
            )
        rows = decision_store.read_window(path, start=start, count=count)
        return DecisionLogRead(
            run_id=run_id,
            total_rows=decision_store.row_count(path),
            start=start,
            log_schema=_schema_to_read(schema),
            rows=[_row_to_read(row, schema) for row in rows],
        )

    def get_decision_summary(self, run_id: str) -> DecisionSummaryRead:
        """Whole-run condition tallies: what was reached, what ever passed."""
        schema = self._decision_schema(run_id)
        path = self._decisions_path(run_id)
        if schema is None or not decision_store.log_exists(path):
            raise NotFoundError(
                f"Run '{run_id}' has no decision log. Re-run it with full "
                "explainability to record one."
            )
        return DecisionSummaryRead(
            run_id=run_id,
            total_rows=decision_store.row_count(path),
            conditions=[
                ConditionSummaryRead(
                    name=str(item["name"]),
                    expected=str(item["expected"]),
                    evaluated=int(item["evaluated"]),
                    passed=int(item["passed"]),
                )
                for item in decision_store.condition_summary(path, schema)
            ],
        )

    def _decisions_path(self, run_id: str) -> Path:
        return self.paths.run_decisions_parquet(run_id)

    def _decision_schema(self, run_id: str) -> DecisionSchema | None:
        cached = self._schema_cache.get(run_id)
        if cached is not None:
            return cached
        row = self.repo.get(run_id)
        if row is None:
            raise NotFoundError(f"Backtest run '{run_id}' not found")
        raw = row[0].decision_schema_json
        if not raw:
            return None
        schema = DecisionSchema.from_dict(json.loads(raw))
        self._schema_cache[run_id] = schema
        return schema

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


#: Rendered in place of the per-bar prose the columnar log deliberately drops.
#: The author's sentence ("fast 1020.2934 vs slow 1021.4290") was a re-statement
#: of numbers now carried as indicator and operand columns, so the verdict is
#: rendered here and the numbers are returned alongside it rather than inside it.
_ACTUAL_PASSED = "Yes"
_ACTUAL_FAILED = "No"
_ACTUAL_UNEVALUATED = "Not evaluated on this bar"


def _conditions_from_log(
    conditions: dict[str, bool | None],
    schema: DecisionSchema,
) -> list[ConditionTraceRead]:
    """Rebuild condition traces from a log row plus the run's constants.

    Schema order is evaluation order, so conditions come back in the order the
    strategy ran them - including the ones it never reached on this bar, which
    are the interesting ones when asking why a rule did not fire.
    """
    traces: list[ConditionTraceRead] = []
    for definition in schema.conditions:
        if definition.name not in conditions:
            continue
        passed = conditions[definition.name]
        traces.append(
            ConditionTraceRead(
                name=definition.name,
                actual_value=(
                    _ACTUAL_UNEVALUATED
                    if passed is None
                    else (_ACTUAL_PASSED if passed else _ACTUAL_FAILED)
                ),
                expected_value=definition.expected,
                passed=bool(passed),
                evaluated=passed is not None,
            )
        )
    return traces


def _operands_from_log(
    operands: dict[str, float],
    schema: DecisionSchema,
) -> list[OperandRead]:
    known = {definition.name: definition for definition in schema.operands}
    reads: list[OperandRead] = []
    for name, definition in known.items():
        if name in operands:
            reads.append(
                OperandRead(
                    name=name,
                    label=definition.label,
                    unit=definition.unit,
                    value=operands[name],
                )
            )
    # An operand recorded but missing from the schema would otherwise vanish.
    for name, value in operands.items():
        if name not in known:
            reads.append(OperandRead(name=name, label=name, unit="", value=value))
    return reads


def _schema_to_read(schema: DecisionSchema) -> DecisionSchemaRead:
    return DecisionSchemaRead.model_validate(schema.to_dict())


def _row_to_read(row: dict[str, Any], schema: DecisionSchema) -> DecisionRowRead:
    indicators, conditions, operands = decision_store.split_columns(row)
    return DecisionRowRead(
        bar_index=int(row[BAR_INDEX_COLUMN]),
        ts=int(row[TIMESTAMP_COLUMN]),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        volume=float(row["volume"]),
        indicators=indicators,
        conditions=conditions,
        operands=_operands_from_log(operands, schema),
    )


def _bar_inspection_to_read(
    inspection: BarInspection,
    bar_events: tuple[ExplainEvent, ...],
    *,
    conditions: list[ConditionTraceRead] | None = None,
    indicators: dict[str, float | str] | None = None,
    operands: list[OperandRead] | None = None,
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
                "indicators": (
                    inspection.market_state.indicators if indicators is None else indicators
                ),
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
            "conditions": (
                [asdict(condition) for condition in inspection.conditions]
                if conditions is None
                else [condition.model_dump() for condition in conditions]
            ),
            "operands": [operand.model_dump() for operand in (operands or [])],
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
