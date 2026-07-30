"""Observe execution and emit structured explain events.

The collector never influences engine behaviour — it only records facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from app.domain.conditions import ConditionSnapshot
from app.domain.enums import PositionSide
from app.domain.explain import (
    EXPLAIN_SCHEMA_VERSION,
    ExplainEvent,
    ExplainEventStatus,
    ExplainEventType,
    ExplainLayer,
    ExplainLevel,
)
from app.domain.money import mul_money, round_money
from app.domain.reason_codes import ReasonCode, normalize_reason_code, rejection_reason_code
from app.engine.execution.order import Order
from app.engine.execution.trade import Trade
from app.engine.explain import messages


@dataclass
class _PositionObservation:
  side: PositionSide
  quantity: float
  entry_price: float
  position_id: int
  entry_order_id: int
  max_favorable: float = 0.0
  max_adverse: float = 0.0


@dataclass
class ExplainCollector:
    """Append-only structured event recorder for one backtest run."""

    level: ExplainLevel
    _events: list[ExplainEvent] = field(default_factory=list)
    _next_seq: int = 1
    _clock_ms: int = 0
    _instrument: str | None = None
    _timeframe: str | None = None
    _position_counter: int = 0
    _active_position: _PositionObservation | None = None

    def __init__(self, level: ExplainLevel) -> None:
        self.level = level
        self._events = []
        self._next_seq = 1
        self._clock_ms = 0
        self._instrument = None
        self._timeframe = None
        self._position_counter = 0
        self._active_position = None

    @property
    def events(self) -> tuple[ExplainEvent, ...]:
        return tuple(self._events)

    @classmethod
    def disabled(cls) -> ExplainCollector:
        return cls(ExplainLevel.NONE)

    @property
    def enabled(self) -> bool:
        return self.level is not ExplainLevel.NONE

    @property
    def records_bar_events(self) -> bool:
        return self.level is ExplainLevel.FULL

    @property
    def clock_ms(self) -> int:
        return self._clock_ms

    def set_context(self, *, instrument: str | None, timeframe: str | None) -> None:
        self._instrument = instrument
        self._timeframe = timeframe

    def merge(self, other: ExplainCollector) -> ExplainCollector:
        """Return a new collector with events from both, renumbered in order."""
        if not self.enabled and not other.enabled:
            return ExplainCollector.disabled()
        combined = [*self._events, *other._events]
        renumbered: list[ExplainEvent] = []
        for index, event in enumerate(combined, start=1):
            renumbered.append(replace(event, seq=index, event_id=_event_id(index)))
        merged = ExplainCollector(self.level if self.enabled else other.level)
        merged._events = renumbered
        merged._next_seq = len(renumbered) + 1
        merged._clock_ms = max(self._clock_ms, other._clock_ms)
        merged._instrument = self._instrument or other._instrument
        merged._timeframe = self._timeframe or other._timeframe
        return merged

    def extend(self, events: tuple[ExplainEvent, ...]) -> None:
        for event in events:
            self._append_event(
                event_type=event.event_type,
                layer=event.layer,
                timestamp_ms=event.timestamp_ms,
                bar_index=event.bar_index,
                reason_code=event.reason_code,
                status=event.status,
                order_id=event.order_id,
                trade_id=event.trade_id,
                position_id=event.position_id,
                message=event.message,
                price=event.price,
                quantity=event.quantity,
                commission=event.commission,
                slippage=event.slippage,
                cash=event.cash,
                portfolio_value=event.portfolio_value,
                pnl=event.pnl,
                metadata=event.metadata,
            )

    def set_clock(self, timestamp_ms: int) -> None:
        self._clock_ms = timestamp_ms

    def record_run_started(self, *, bar_count: int) -> None:
        if not self.enabled:
            return
        self._append_event(
            event_type=ExplainEventType.RUN_STARTED,
            layer=ExplainLayer.SYSTEM,
            timestamp_ms=self._clock_ms,
            bar_index=None,
            reason_code=ReasonCode.SYSTEM_RUN_STARTED,
            status=ExplainEventStatus.INFO,
            message=messages.run_started_message(bar_count=bar_count),
            metadata={"bar_count": bar_count},
        )

    def record_strategy_loaded(self) -> None:
        if not self.enabled:
            return
        self._append_event(
            event_type=ExplainEventType.STRATEGY_LOADED,
            layer=ExplainLayer.SYSTEM,
            timestamp_ms=self._clock_ms,
            bar_index=None,
            reason_code=ReasonCode.SYSTEM_STRATEGY_LOADED,
            status=ExplainEventStatus.OK,
            message=messages.strategy_loaded_message(),
        )

    def record_strategy_load_failed(self, *, detail: str) -> None:
        if not self.enabled:
            return
        self._append_event(
            event_type=ExplainEventType.STRATEGY_LOADED,
            layer=ExplainLayer.SYSTEM,
            timestamp_ms=self._clock_ms,
            bar_index=None,
            reason_code=ReasonCode.SYSTEM_STRATEGY_LOAD_FAILED,
            status=ExplainEventStatus.FAILED,
            message=messages.strategy_load_failed_message(detail=detail),
            metadata={"detail": detail},
        )

    def record_parameters_applied(
        self,
        *,
        initial_capital: float,
        commission: float,
        slippage: float,
    ) -> None:
        if not self.enabled:
            return
        self._append_event(
            event_type=ExplainEventType.PARAMETERS_APPLIED,
            layer=ExplainLayer.SYSTEM,
            timestamp_ms=self._clock_ms,
            bar_index=None,
            reason_code=ReasonCode.SYSTEM_PARAMETERS_LOADED,
            status=ExplainEventStatus.OK,
            message=messages.parameters_applied_message(
                initial_capital=initial_capital,
                commission=commission,
                slippage=slippage,
            ),
            cash=initial_capital,
            portfolio_value=initial_capital,
            metadata={
                "initial_capital": initial_capital,
                "commission": commission,
                "slippage": slippage,
            },
        )

    def record_dataset_loaded(self, *, bar_count: int, dataset_name: str) -> None:
        if not self.enabled:
            return
        self._append_event(
            event_type=ExplainEventType.DATASET_LOADED,
            layer=ExplainLayer.SYSTEM,
            timestamp_ms=self._clock_ms,
            bar_index=None,
            reason_code=ReasonCode.SYSTEM_DATASET_LOADED,
            status=ExplainEventStatus.OK,
            message=messages.dataset_loaded_message(
                bar_count=bar_count,
                dataset_name=dataset_name,
            ),
            metadata={"bar_count": bar_count, "dataset_name": dataset_name},
        )

    def record_bar_processing_started(self, *, bar_index: int, timestamp_ms: int) -> None:
        if not self.records_bar_events:
            return
        self._append_event(
            event_type=ExplainEventType.BAR_PROCESSING_STARTED,
            layer=ExplainLayer.EXECUTION,
            timestamp_ms=timestamp_ms,
            bar_index=bar_index,
            reason_code=ReasonCode.SYSTEM_BAR_PROCESSING,
            status=ExplainEventStatus.INFO,
            message=messages.bar_processing_started_message(bar_index=bar_index),
        )

    def record_conditions_evaluated(
        self,
        snapshot: ConditionSnapshot,
        *,
        timestamp_ms: int,
    ) -> None:
        if not self.enabled:
            return
        passed_count = sum(1 for condition in snapshot.conditions if condition.passed)
        total_count = len(snapshot.conditions)
        self._append_event(
            event_type=ExplainEventType.CONDITIONS_EVALUATED,
            layer=ExplainLayer.DECISION,
            timestamp_ms=timestamp_ms,
            bar_index=snapshot.bar_index,
            reason_code=ReasonCode.DECISION_CONDITIONS_EVALUATED,
            status=ExplainEventStatus.INFO,
            message=messages.conditions_evaluated_message(
                bar_index=snapshot.bar_index,
                passed_count=passed_count,
                total_count=total_count,
            ),
            metadata=snapshot.to_metadata(),
        )

    def record_signal_generated(
        self,
        *,
        action: str,
        quantity: float,
        bar_index: int,
        timestamp_ms: int,
        accepted: bool,
        rejection_reason: str | None = None,
    ) -> None:
        if not self.enabled:
            return
        if self.level is ExplainLevel.TRADES_ONLY and not accepted:
            return
        status = ExplainEventStatus.OK if accepted else ExplainEventStatus.REJECTED
        reason_code = _signal_reason_code(action, accepted=accepted)
        message = (
            messages.signal_generated_message(
                action=action,
                quantity=quantity,
                bar_index=bar_index,
            )
            if accepted
            else messages.signal_rejected_message(
                action=action,
                reason=rejection_reason or "request ignored",
            )
        )
        self._append_event(
            event_type=ExplainEventType.SIGNAL_GENERATED,
            layer=ExplainLayer.DECISION,
            timestamp_ms=timestamp_ms,
            bar_index=bar_index,
            reason_code=reason_code,
            status=status,
            quantity=quantity if accepted else None,
            message=message,
            metadata={
                "action": action,
                "accepted": accepted,
                "rejection_reason": rejection_reason,
            },
        )

    def record_order_created(self, order: Order) -> None:
        if not self.enabled:
            return
        self._append_event(
            event_type=ExplainEventType.ORDER_CREATED,
            layer=ExplainLayer.EXECUTION,
            timestamp_ms=order.submitted_ts,
            bar_index=order.submitted_bar_index,
            reason_code=ReasonCode.ORDER_CREATED,
            status=ExplainEventStatus.OK,
            order_id=order.id,
            quantity=order.quantity,
            message=messages.order_created_message(
                order_type=order.order_type,
                quantity=order.quantity,
            ),
            metadata={"order_type": order.order_type.value},
        )

    def record_order_submitted(self, order: Order) -> None:
        if not self.enabled:
            return
        self._append_event(
            event_type=ExplainEventType.ORDER_SUBMITTED,
            layer=ExplainLayer.EXECUTION,
            timestamp_ms=order.submitted_ts,
            bar_index=order.submitted_bar_index,
            reason_code=ReasonCode.ORDER_SUBMITTED,
            status=ExplainEventStatus.OK,
            order_id=order.id,
            quantity=order.quantity,
            message=messages.order_submitted_message(
                order_type=order.order_type,
                quantity=order.quantity,
            ),
            metadata={"order_type": order.order_type.value},
        )
        self._append_narrative(
            timestamp_ms=order.submitted_ts,
            bar_index=order.submitted_bar_index,
            reason_code=f"narrative.{ReasonCode.ORDER_SUBMITTED}",
            order_id=order.id,
            message=messages.order_submitted_message(
                order_type=order.order_type,
                quantity=order.quantity,
            ),
        )

    def record_order_filled(
        self,
        order: Order,
        *,
        cash: float,
        portfolio_value: float,
    ) -> None:
        if not self.enabled:
            return
        assert order.fill_price is not None
        assert order.filled_bar_index is not None
        assert order.fill_ts is not None
        self._append_event(
            event_type=ExplainEventType.ORDER_FILLED,
            layer=ExplainLayer.EXECUTION,
            timestamp_ms=order.fill_ts,
            bar_index=order.filled_bar_index,
            reason_code=ReasonCode.ORDER_FILLED,
            status=ExplainEventStatus.OK,
            order_id=order.id,
            price=order.fill_price,
            quantity=order.quantity,
            commission=order.commission,
            slippage=order.slippage_cost,
            cash=cash,
            portfolio_value=portfolio_value,
            message=messages.order_filled_message(
                order_type=order.order_type,
                fill_price=order.fill_price,
            ),
            metadata={"order_type": order.order_type.value},
        )
        self._append_narrative(
            timestamp_ms=order.fill_ts,
            bar_index=order.filled_bar_index,
            reason_code=f"narrative.{ReasonCode.ORDER_FILLED}",
            order_id=order.id,
            message=messages.order_filled_message(
                order_type=order.order_type,
                fill_price=order.fill_price,
            ),
        )

    def record_order_rejected(self, order: Order) -> None:
        if not self.enabled:
            return
        reason = order.rejection_reason or "unknown reason"
        reason_code = rejection_reason_code(reason)
        self._append_event(
            event_type=ExplainEventType.ORDER_REJECTED,
            layer=ExplainLayer.EXECUTION,
            timestamp_ms=order.submitted_ts,
            bar_index=order.submitted_bar_index,
            reason_code=reason_code,
            status=ExplainEventStatus.REJECTED,
            order_id=order.id,
            quantity=order.quantity,
            message=messages.order_rejected_message(
                order_type=order.order_type,
                reason=reason,
            ),
            metadata={"order_type": order.order_type.value, "rejection_reason": reason},
        )
        self._append_narrative(
            timestamp_ms=order.submitted_ts,
            bar_index=order.submitted_bar_index,
            reason_code="narrative.order_rejected",
            order_id=order.id,
            message=messages.order_rejected_message(
                order_type=order.order_type,
                reason=reason,
            ),
        )

    def record_position_opened(
        self,
        *,
        side: PositionSide,
        quantity: float,
        price: float,
        bar_index: int,
        timestamp_ms: int,
        order_id: int,
        cash: float,
        portfolio_value: float,
    ) -> None:
        if not self.enabled:
            return
        self._position_counter += 1
        position_id = self._position_counter
        self._active_position = _PositionObservation(
            side=side,
            quantity=quantity,
            entry_price=price,
            position_id=position_id,
            entry_order_id=order_id,
        )
        self._append_event(
            event_type=ExplainEventType.POSITION_OPENED,
            layer=ExplainLayer.EXECUTION,
            timestamp_ms=timestamp_ms,
            bar_index=bar_index,
            reason_code=ReasonCode.POSITION_OPENED,
            status=ExplainEventStatus.OK,
            order_id=order_id,
            position_id=position_id,
            price=price,
            quantity=quantity,
            cash=cash,
            portfolio_value=portfolio_value,
            message=messages.position_opened_message(
                side=side,
                quantity=quantity,
                price=price,
            ),
            metadata={"side": side.value},
        )
        self._append_narrative(
            timestamp_ms=timestamp_ms,
            bar_index=bar_index,
            reason_code=f"narrative.{ReasonCode.POSITION_OPENED}",
            order_id=order_id,
            message=messages.position_opened_message(
                side=side,
                quantity=quantity,
                price=price,
            ),
        )

    def record_position_updated(
        self,
        *,
        bar_index: int,
        timestamp_ms: int,
        mark_price: float,
        cash: float,
        portfolio_value: float,
        unrealized_pnl: float,
    ) -> None:
        if not self.enabled or self._active_position is None:
            return
        if not self.records_bar_events:
            return
        position = self._active_position
        if unrealized_pnl > position.max_favorable:
            position.max_favorable = unrealized_pnl
        if unrealized_pnl < position.max_adverse:
            position.max_adverse = unrealized_pnl

        self._append_event(
            event_type=ExplainEventType.POSITION_UPDATED,
            layer=ExplainLayer.EXECUTION,
            timestamp_ms=timestamp_ms,
            bar_index=bar_index,
            reason_code=ReasonCode.POSITION_UPDATED,
            status=ExplainEventStatus.OK,
            order_id=position.entry_order_id,
            position_id=position.position_id,
            price=mark_price,
            quantity=position.quantity,
            cash=cash,
            portfolio_value=portfolio_value,
            pnl=unrealized_pnl,
            message=messages.position_updated_message(
                side=position.side,
                mark_price=mark_price,
                unrealized_pnl=unrealized_pnl,
            ),
            metadata={
                "side": position.side.value,
                "unrealized_pnl": unrealized_pnl,
                "mae_running": position.max_adverse,
                "mfe_running": position.max_favorable,
            },
        )

    def record_position_closed(
        self,
        *,
        side: PositionSide,
        quantity: float,
        price: float,
        bar_index: int,
        timestamp_ms: int,
        order_id: int,
        trade_seq: int,
        cash: float,
        portfolio_value: float,
    ) -> None:
        if not self.enabled:
            return
        position_id = self._active_position.position_id if self._active_position else None
        self._append_event(
            event_type=ExplainEventType.POSITION_CLOSED,
            layer=ExplainLayer.EXECUTION,
            timestamp_ms=timestamp_ms,
            bar_index=bar_index,
            reason_code=ReasonCode.POSITION_CLOSED,
            status=ExplainEventStatus.OK,
            order_id=order_id,
            trade_id=trade_seq,
            position_id=position_id,
            price=price,
            quantity=quantity,
            cash=cash,
            portfolio_value=portfolio_value,
            message=messages.position_closed_message(
                side=side,
                quantity=quantity,
                price=price,
            ),
            metadata={"side": side.value},
        )
        self._append_narrative(
            timestamp_ms=timestamp_ms,
            bar_index=bar_index,
            reason_code=f"narrative.{ReasonCode.POSITION_CLOSED}",
            order_id=order_id,
            trade_id=trade_seq,
            message=messages.position_closed_message(
                side=side,
                quantity=quantity,
                price=price,
            ),
        )

    def record_profit_calculated(
        self, trade: Trade, *, cash: float, portfolio_value: float
    ) -> None:
        if not self.enabled:
            return
        mae = self._active_position.max_adverse if self._active_position else None
        mfe = self._active_position.max_favorable if self._active_position else None
        notional = trade.entry_price * trade.quantity
        return_pct = (trade.net_pnl / notional * 100.0) if notional > 0 else 0.0

        self._append_event(
            event_type=ExplainEventType.PROFIT_CALCULATED,
            layer=ExplainLayer.EXECUTION,
            timestamp_ms=trade.exit_ts,
            bar_index=None,
            reason_code=ReasonCode.SYSTEM_PROFIT_CALCULATED,
            status=ExplainEventStatus.OK,
            trade_id=trade.seq,
            price=trade.exit_price,
            quantity=trade.quantity,
            commission=trade.commission,
            slippage=trade.slippage_cost,
            cash=cash,
            portfolio_value=portfolio_value,
            pnl=trade.net_pnl,
            message=messages.profit_calculated_message(
                trade_seq=trade.seq,
                net_pnl=trade.net_pnl,
            ),
            metadata={
                "gross_pnl": trade.gross_pnl,
                "net_pnl": trade.net_pnl,
                "return_pct": round(return_pct, 4),
                "mae": mae,
                "mfe": mfe,
                "bars_held": trade.bars_held,
                "side": trade.side.value,
            },
        )
        self._active_position = None

    def record_metrics_generated(self, *, trade_count: int) -> None:
        if not self.enabled:
            return
        self._append_event(
            event_type=ExplainEventType.METRICS_GENERATED,
            layer=ExplainLayer.SYSTEM,
            timestamp_ms=self._clock_ms,
            bar_index=None,
            reason_code=ReasonCode.SYSTEM_METRICS_GENERATED,
            status=ExplainEventStatus.OK,
            message=messages.metrics_generated_message(trade_count=trade_count),
            metadata={"trade_count": trade_count},
        )

    def record_charts_generated(self, *, candle_count: int, marker_count: int) -> None:
        if not self.enabled:
            return
        self._append_event(
            event_type=ExplainEventType.CHARTS_GENERATED,
            layer=ExplainLayer.SYSTEM,
            timestamp_ms=self._clock_ms,
            bar_index=None,
            reason_code=ReasonCode.SYSTEM_CHARTS_GENERATED,
            status=ExplainEventStatus.OK,
            message=messages.charts_generated_message(
                candle_count=candle_count,
                marker_count=marker_count,
            ),
            metadata={"candle_count": candle_count, "marker_count": marker_count},
        )

    def record_run_completed(self, *, completed: bool, trade_count: int) -> None:
        if not self.enabled:
            return
        status = ExplainEventStatus.OK if completed else ExplainEventStatus.FAILED
        self._append_event(
            event_type=ExplainEventType.RUN_COMPLETED,
            layer=ExplainLayer.SYSTEM,
            timestamp_ms=self._clock_ms,
            bar_index=None,
            reason_code=ReasonCode.SYSTEM_COMPLETED,
            status=status,
            message=messages.run_completed_message(
                completed=completed,
                trade_count=trade_count,
            ),
            metadata={"completed": completed, "trade_count": trade_count},
        )

    def observe_open_position(
        self,
        *,
        bar_index: int,
        timestamp_ms: int,
        mark_price: float,
        cash: float,
        side: PositionSide,
        quantity: float,
        entry_price: float,
    ) -> None:
        """Observation-only mark-to-market for open positions."""
        if not self.enabled or self._active_position is None:
            return
        if side is PositionSide.LONG:
            unrealized = round_money(mul_money(mark_price - entry_price, quantity))
            position_value = round_money(mul_money(mark_price, quantity))
            portfolio_value = round_money(cash + position_value)
        else:
            unrealized = round_money(mul_money(entry_price - mark_price, quantity))
            portfolio_value = round_money(cash)
        self.record_position_updated(
            bar_index=bar_index,
            timestamp_ms=timestamp_ms,
            mark_price=mark_price,
            cash=cash,
            portfolio_value=portfolio_value,
            unrealized_pnl=unrealized,
        )

    def _append_narrative(
        self,
        *,
        timestamp_ms: int,
        bar_index: int | None,
        reason_code: str,
        message: str,
        order_id: int | None = None,
        trade_id: int | None = None,
    ) -> None:
        self._append_event(
            event_type=ExplainEventType.HUMAN_NARRATIVE,
            layer=ExplainLayer.NARRATIVE,
            timestamp_ms=timestamp_ms,
            bar_index=bar_index,
            reason_code=reason_code,
            status=ExplainEventStatus.INFO,
            order_id=order_id,
            trade_id=trade_id,
            message=message,
        )

    def _append_event(
        self,
        *,
        event_type: ExplainEventType,
        layer: ExplainLayer,
        timestamp_ms: int,
        bar_index: int | None,
        reason_code: str,
        status: ExplainEventStatus,
        message: str,
        order_id: int | None = None,
        trade_id: int | None = None,
        position_id: int | None = None,
        price: float | None = None,
        quantity: float | None = None,
        commission: float | None = None,
        slippage: float | None = None,
        cash: float | None = None,
        portfolio_value: float | None = None,
        pnl: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        seq = self._next_seq
        self._events.append(
            ExplainEvent(
                seq=seq,
                event_type=event_type,
                layer=layer,
                timestamp_ms=timestamp_ms,
                bar_index=bar_index,
                reason_code=normalize_reason_code(reason_code),
                status=status,
                message=message,
                schema_version=EXPLAIN_SCHEMA_VERSION,
                event_id=_event_id(seq),
                order_id=order_id,
                trade_id=trade_id,
                position_id=position_id,
                instrument=self._instrument,
                timeframe=self._timeframe,
                price=price,
                quantity=quantity,
                commission=commission,
                slippage=slippage,
                cash=cash,
                portfolio_value=portfolio_value,
                pnl=pnl,
                metadata=metadata or {},
            )
        )
        self._next_seq += 1


def _event_id(seq: int) -> str:
    return f"evt-{seq:06d}"


def _signal_reason_code(action: str, *, accepted: bool) -> str:
    if not accepted:
        return ReasonCode.SIGNAL_REJECTED
    lowered = action.lower()
    if lowered in {"buy", "long"}:
        return ReasonCode.SIGNAL_LONG
    if lowered in {"sell short", "sell_short", "short"}:
        return ReasonCode.SIGNAL_SHORT
    if lowered in {"close", "exit"}:
        return ReasonCode.SIGNAL_EXIT
    return ReasonCode.SIGNAL_REJECTED
