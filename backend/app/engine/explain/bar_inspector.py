"""Reconstruct bar-level inspection from persisted run data and explain events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from app.domain.conditions import ConditionSnapshot, ConditionTrace
from app.domain.explain import ExplainEvent, ExplainEventType, ExplainLayer
from app.domain.reason_codes import ReasonCode
from app.engine.explain.event_index import EventIndex


class DecisionType(StrEnum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    EXIT = "exit"
    NO_TRADE = "no_trade"
    REJECTED = "rejected"


@dataclass(frozen=True)
class BarCandle:
    bar_index: int
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class BarOrderSummary:
    order_ref: int
    order_type: str
    quantity: float
    status: str
    fill_price: float | None
    commission: float
    slippage_cost: float


@dataclass(frozen=True)
class BarPositionSummary:
    side: str
    quantity: float
    entry_price: float


@dataclass(frozen=True)
class BarMarketState:
    current_price: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    trend: str
    volatility_pct: float
    session: str
    indicators: dict[str, float | str]
    cash: float | None
    portfolio_value: float | None
    position: BarPositionSummary | None


@dataclass(frozen=True)
class BarDecision:
    decision_type: DecisionType
    reason_code: str
    message: str
    related_event_seqs: tuple[int, ...]


@dataclass(frozen=True)
class BarExecutionSummary:
    occurred: bool
    message: str
    order_ref: int | None
    fill_price: float | None
    quantity: float | None
    commission: float | None
    slippage: float | None
    position: BarPositionSummary | None
    pnl: float | None


@dataclass(frozen=True)
class BarTimelineStep:
    label: str
    event_type: ExplainEventType
    event_seq: int
    timestamp_ms: int


@dataclass(frozen=True)
class BarNavigation:
    bar_index: int
    bar_count: int
    previous_bar_index: int | None
    next_bar_index: int | None
    first_signal_bar: int | None
    last_signal_bar: int | None
    trade_entry_bars: tuple[int, ...]
    trade_exit_bars: tuple[int, ...]


@dataclass(frozen=True)
class BarInspection:
    bar_index: int
    candle: BarCandle
    market_state: BarMarketState
    conditions: tuple[ConditionTrace, ...]
    decision: BarDecision
    execution: BarExecutionSummary
    timeline: tuple[BarTimelineStep, ...]
    open_orders: tuple[BarOrderSummary, ...]
    filled_orders: tuple[BarOrderSummary, ...]
    cancelled_orders: tuple[BarOrderSummary, ...]
    event_seqs: tuple[int, ...]
    navigation: BarNavigation


_TIMELINE_EVENT_TYPES = (
    ExplainEventType.CONDITIONS_EVALUATED,
    ExplainEventType.SIGNAL_GENERATED,
    ExplainEventType.ORDER_CREATED,
    ExplainEventType.ORDER_SUBMITTED,
    ExplainEventType.ORDER_FILLED,
    ExplainEventType.ORDER_REJECTED,
    ExplainEventType.POSITION_OPENED,
    ExplainEventType.POSITION_UPDATED,
    ExplainEventType.POSITION_CLOSED,
    ExplainEventType.PROFIT_CALCULATED,
)

_TIMELINE_LABELS: dict[ExplainEventType, str] = {
    ExplainEventType.CONDITIONS_EVALUATED: "Conditions Evaluated",
    ExplainEventType.SIGNAL_GENERATED: "Signal Generated",
    ExplainEventType.ORDER_CREATED: "Order Created",
    ExplainEventType.ORDER_SUBMITTED: "Order Submitted",
    ExplainEventType.ORDER_FILLED: "Order Filled",
    ExplainEventType.ORDER_REJECTED: "Order Rejected",
    ExplainEventType.POSITION_OPENED: "Position Opened",
    ExplainEventType.POSITION_UPDATED: "Position Updated",
    ExplainEventType.POSITION_CLOSED: "Position Closed",
    ExplainEventType.PROFIT_CALCULATED: "Profit Calculated",
}


def inspect_bar(
    *,
    bar_index: int,
    candles: list[dict[str, Any]],
    orders: list[dict[str, Any]],
    index: EventIndex,
    navigation: BarNavigation,
) -> BarInspection | None:
    if bar_index < 0 or bar_index >= len(candles):
        return None

    candle = _parse_candle(bar_index, candles[bar_index])
    bar_events = _bar_events(index, bar_index)
    conditions, indicators = _parse_conditions(bar_events, bar_index)
    market_state = _build_market_state(candle, bar_events, indicators)
    decision = _build_decision(bar_events, market_state)
    execution = _build_execution(bar_events, orders, bar_index)
    open_orders, filled_orders, cancelled_orders = _categorize_orders(orders, bar_index)
    timeline = _build_timeline(bar_events)

    return BarInspection(
        bar_index=bar_index,
        candle=candle,
        market_state=market_state,
        conditions=conditions,
        decision=decision,
        execution=execution,
        timeline=timeline,
        open_orders=open_orders,
        filled_orders=filled_orders,
        cancelled_orders=cancelled_orders,
        event_seqs=tuple(event.seq for event in bar_events),
        navigation=navigation,
    )


def build_navigation(
    *,
    bar_index: int,
    bar_count: int,
    index: EventIndex,
) -> BarNavigation:
    signal_bars = sorted(
        {
            event.bar_index
            for event in index.by_event_type.get(ExplainEventType.SIGNAL_GENERATED, ())
            if event.bar_index is not None
        }
    )
    entry_bars = sorted(
        {
            event.bar_index
            for event in index.by_event_type.get(ExplainEventType.POSITION_OPENED, ())
            if event.bar_index is not None
        }
    )
    exit_bars = sorted(
        {
            event.bar_index
            for event in index.by_event_type.get(ExplainEventType.POSITION_CLOSED, ())
            if event.bar_index is not None
        }
    )

    return BarNavigation(
        bar_index=bar_index,
        bar_count=bar_count,
        previous_bar_index=bar_index - 1 if bar_index > 0 else None,
        next_bar_index=bar_index + 1 if bar_index < bar_count - 1 else None,
        first_signal_bar=signal_bars[0] if signal_bars else None,
        last_signal_bar=signal_bars[-1] if signal_bars else None,
        trade_entry_bars=tuple(sorted(set(entry_bars))),
        trade_exit_bars=tuple(sorted(set(exit_bars))),
    )


def _bar_events(index: EventIndex, bar_index: int) -> tuple[ExplainEvent, ...]:
    events = index.by_bar_index.get(bar_index, ())
    return tuple(
        sorted(
            (event for event in events if event.layer is not ExplainLayer.NARRATIVE),
            key=lambda item: (item.timestamp_ms, item.seq),
        )
    )


def _parse_candle(bar_index: int, raw: dict[str, Any]) -> BarCandle:
    return BarCandle(
        bar_index=bar_index,
        ts=int(raw["ts"]),
        open=float(raw["open"]),
        high=float(raw["high"]),
        low=float(raw["low"]),
        close=float(raw["close"]),
        volume=float(raw.get("volume", 0.0)),
    )


def _parse_conditions(
    bar_events: tuple[ExplainEvent, ...], bar_index: int
) -> tuple[tuple[ConditionTrace, ...], dict[str, float | str]]:
    for event in bar_events:
        if event.event_type is ExplainEventType.CONDITIONS_EVALUATED:
            snapshot = ConditionSnapshot.from_metadata(
                bar_index=bar_index,
                metadata=event.metadata,
            )
            return snapshot.conditions, snapshot.indicators
    return (), {}


def _build_market_state(
    candle: BarCandle,
    bar_events: tuple[ExplainEvent, ...],
    indicators: dict[str, float | str],
) -> BarMarketState:
    cash, portfolio_value, position = _portfolio_facts(bar_events)
    trend = "Flat"
    if candle.close > candle.open:
        trend = "Bullish"
    elif candle.close < candle.open:
        trend = "Bearish"
    volatility_pct = 0.0
    if candle.close > 0:
        volatility_pct = round((candle.high - candle.low) / candle.close * 100.0, 4)

    return BarMarketState(
        current_price=candle.close,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
        trend=trend,
        volatility_pct=volatility_pct,
        session=_session_label(candle.ts),
        indicators=indicators,
        cash=cash,
        portfolio_value=portfolio_value,
        position=position,
    )


def _portfolio_facts(
    bar_events: tuple[ExplainEvent, ...],
) -> tuple[float | None, float | None, BarPositionSummary | None]:
    cash: float | None = None
    portfolio_value: float | None = None
    position: BarPositionSummary | None = None

    for event in bar_events:
        if event.cash is not None:
            cash = event.cash
        if event.portfolio_value is not None:
            portfolio_value = event.portfolio_value
        if event.event_type is ExplainEventType.POSITION_OPENED:
            side = str(event.metadata.get("side", "long"))
            position = BarPositionSummary(
                side=side,
                quantity=float(event.quantity or 0.0),
                entry_price=float(event.price or 0.0),
            )
        if event.event_type is ExplainEventType.POSITION_CLOSED:
            position = None
        if event.event_type is ExplainEventType.POSITION_UPDATED and position is not None:
            pass

    return cash, portfolio_value, position


def _build_decision(
    bar_events: tuple[ExplainEvent, ...],
    market_state: BarMarketState,
) -> BarDecision:
    signals = [
        event for event in bar_events if event.event_type is ExplainEventType.SIGNAL_GENERATED
    ]
    if signals:
        signal = signals[-1]
        accepted = bool(signal.metadata.get("accepted", signal.status.value == "ok"))
        if not accepted:
            reason = str(signal.metadata.get("rejection_reason", signal.message))
            return BarDecision(
                decision_type=DecisionType.REJECTED,
                reason_code=signal.reason_code,
                message=reason,
                related_event_seqs=(signal.seq,),
            )
        if signal.reason_code == ReasonCode.SIGNAL_LONG:
            return BarDecision(
                decision_type=DecisionType.BUY,
                reason_code=signal.reason_code,
                message=signal.message,
                related_event_seqs=(signal.seq,),
            )
        if signal.reason_code == ReasonCode.SIGNAL_SHORT:
            return BarDecision(
                decision_type=DecisionType.SELL,
                reason_code=signal.reason_code,
                message=signal.message,
                related_event_seqs=(signal.seq,),
            )
        if signal.reason_code == ReasonCode.SIGNAL_EXIT:
            return BarDecision(
                decision_type=DecisionType.EXIT,
                reason_code=signal.reason_code,
                message=signal.message,
                related_event_seqs=(signal.seq,),
            )

    if market_state.position is not None:
        return BarDecision(
            decision_type=DecisionType.HOLD,
            reason_code=ReasonCode.DECISION_NO_TRADE,
            message="Already holding a position; no new entry signal was generated.",
            related_event_seqs=(),
        )

    return BarDecision(
        decision_type=DecisionType.NO_TRADE,
        reason_code=ReasonCode.DECISION_NO_TRADE,
        message="No trading signal was generated on this bar.",
        related_event_seqs=(),
    )


def _build_execution(
    bar_events: tuple[ExplainEvent, ...],
    orders: list[dict[str, Any]],
    bar_index: int,
) -> BarExecutionSummary:
    fills = [event for event in bar_events if event.event_type is ExplainEventType.ORDER_FILLED]
    if fills:
        fill = fills[-1]
        position = None
        for event in bar_events:
            if event.event_type is ExplainEventType.POSITION_OPENED:
                position = BarPositionSummary(
                    side=str(event.metadata.get("side", "long")),
                    quantity=float(event.quantity or 0.0),
                    entry_price=float(event.price or 0.0),
                )
            if event.event_type is ExplainEventType.POSITION_CLOSED:
                position = None
        pnl = None
        for event in bar_events:
            if event.event_type is ExplainEventType.PROFIT_CALCULATED:
                pnl = event.pnl
        return BarExecutionSummary(
            occurred=True,
            message=fill.message,
            order_ref=fill.order_id,
            fill_price=fill.price,
            quantity=fill.quantity,
            commission=fill.commission,
            slippage=fill.slippage,
            position=position,
            pnl=pnl,
        )

    rejections = [
        event for event in bar_events if event.event_type is ExplainEventType.ORDER_REJECTED
    ]
    if rejections:
        rejected = rejections[-1]
        return BarExecutionSummary(
            occurred=False,
            message=rejected.message,
            order_ref=rejected.order_id,
            fill_price=None,
            quantity=rejected.quantity,
            commission=None,
            slippage=None,
            position=None,
            pnl=None,
        )

    submitted = [
        event for event in bar_events if event.event_type is ExplainEventType.ORDER_SUBMITTED
    ]
    if submitted:
        order = submitted[-1]
        return BarExecutionSummary(
            occurred=False,
            message="Order was submitted and is queued for fill at the next bar open.",
            order_ref=order.order_id,
            fill_price=None,
            quantity=order.quantity,
            commission=None,
            slippage=None,
            position=None,
            pnl=None,
        )

    pending_on_bar = [
        item
        for item in orders
        if int(item.get("submitted_bar_index", -1)) == bar_index and item.get("status") == "pending"
    ]
    if pending_on_bar:
        return BarExecutionSummary(
            occurred=False,
            message="Orders were submitted on this bar and await the next open.",
            order_ref=int(pending_on_bar[-1]["id"]),
            fill_price=None,
            quantity=float(pending_on_bar[-1]["quantity"]),
            commission=None,
            slippage=None,
            position=None,
            pnl=None,
        )

    return BarExecutionSummary(
        occurred=False,
        message="No execution occurred on this bar.",
        order_ref=None,
        fill_price=None,
        quantity=None,
        commission=None,
        slippage=None,
        position=None,
        pnl=None,
    )


def _categorize_orders(
    orders: list[dict[str, Any]], bar_index: int
) -> tuple[tuple[BarOrderSummary, ...], tuple[BarOrderSummary, ...], tuple[BarOrderSummary, ...]]:
    open_orders: list[BarOrderSummary] = []
    filled_orders: list[BarOrderSummary] = []
    cancelled_orders: list[BarOrderSummary] = []

    for raw in orders:
        summary = _order_summary(raw)
        submitted = int(raw.get("submitted_bar_index", -1))
        filled = raw.get("filled_bar_index")
        status = str(raw.get("status", ""))
        if submitted == bar_index and status == "pending":
            open_orders.append(summary)
        if filled is not None and int(filled) == bar_index and status == "filled":
            filled_orders.append(summary)
        if submitted == bar_index and status == "rejected":
            cancelled_orders.append(summary)

    return tuple(open_orders), tuple(filled_orders), tuple(cancelled_orders)


def _order_summary(raw: dict[str, Any]) -> BarOrderSummary:
    fill_price = raw.get("fill_price")
    return BarOrderSummary(
        order_ref=int(raw["id"]),
        order_type=str(raw["order_type"]),
        quantity=float(raw["quantity"]),
        status=str(raw["status"]),
        fill_price=float(fill_price) if fill_price is not None else None,
        commission=float(raw.get("commission", 0.0)),
        slippage_cost=float(raw.get("slippage_cost", 0.0)),
    )


def _build_timeline(bar_events: tuple[ExplainEvent, ...]) -> tuple[BarTimelineStep, ...]:
    steps: list[BarTimelineStep] = []
    for event_type in _TIMELINE_EVENT_TYPES:
        for event in bar_events:
            if event.event_type is event_type:
                steps.append(
                    BarTimelineStep(
                        label=_TIMELINE_LABELS.get(event_type, event_type.value),
                        event_type=event_type,
                        event_seq=event.seq,
                        timestamp_ms=event.timestamp_ms,
                    )
                )
    return tuple(steps)


def _session_label(ts_ms: int) -> str:
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
    hour = dt.hour
    if 9 <= hour < 16:
        return "Regular Session"
    if hour < 9:
        return "Pre-Market"
    return "After Hours"
