"""Reconstruct trades and timelines purely from explainability events."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.explain import ExplainEvent, ExplainEventType
from app.engine.explain.event_index import EventIndex


class TradeOutcome(StrEnum):
    WINNING = "winning"
    LOSING = "losing"
    BREAK_EVEN = "break_even"


@dataclass(frozen=True)
class TradeTimelineStep:
    """One step in a trade's execution graph."""

    step_type: ExplainEventType
    label: str
    event_seq: int
    timestamp_ms: int
    bar_index: int | None
    price: float | None
    quantity: float | None
    commission: float | None
    slippage: float | None
    cash: float | None
    portfolio_value: float | None
    reason_code: str
    message: str
    related_event_seqs: tuple[int, ...]


@dataclass(frozen=True)
class TradeSummary:
    trade_number: int
    direction: str
    entry_time_ms: int
    exit_time_ms: int
    entry_price: float
    exit_price: float
    gross_profit: float
    net_profit: float
    commission: float
    slippage: float
    holding_period_bars: int
    mae: float | None
    mfe: float | None
    return_pct: float
    risk_reward: float | None
    status: TradeOutcome
    order_ids: tuple[int, ...]
    position_id: int | None
    event_count: int


@dataclass(frozen=True)
class TradeInspection:
    summary: TradeSummary
    timeline: tuple[TradeTimelineStep, ...]
    event_seqs: tuple[int, ...]


_STEP_LABELS: dict[ExplainEventType, str] = {
    ExplainEventType.SIGNAL_GENERATED: "Signal Generated",
    ExplainEventType.ORDER_CREATED: "Order Created",
    ExplainEventType.ORDER_SUBMITTED: "Order Submitted",
    ExplainEventType.ORDER_FILLED: "Order Filled",
    ExplainEventType.POSITION_OPENED: "Position Opened",
    ExplainEventType.POSITION_UPDATED: "Position Updated",
    ExplainEventType.POSITION_CLOSED: "Position Closed",
    ExplainEventType.PROFIT_CALCULATED: "Profit Calculated",
}


def inspect_trade(index: EventIndex, trade_id: int) -> TradeInspection | None:
    """Build a full trade inspection from indexed explain events."""
    trade_events = index.by_trade_id.get(trade_id)
    if not trade_events:
        return None

    related_orders = index.order_ids_for_trade(trade_id)
    graph_events = _collect_trade_graph(index, trade_id, related_orders)
    timeline = _build_timeline(graph_events, trade_id)
    summary = _build_summary(trade_id, graph_events, timeline, related_orders)
    return TradeInspection(
        summary=summary,
        timeline=timeline,
        event_seqs=tuple(event.seq for event in graph_events),
    )


def list_trade_summaries(index: EventIndex) -> tuple[TradeSummary, ...]:
    return tuple(
        inspection.summary
        for trade_id in index.trade_ids()
        if (inspection := inspect_trade(index, trade_id)) is not None
    )


def _collect_trade_graph(
    index: EventIndex, trade_id: int, order_ids: tuple[int, ...]
) -> tuple[ExplainEvent, ...]:
    seen: dict[int, ExplainEvent] = {}

    for event in index.by_trade_id.get(trade_id, ()):
        seen[event.seq] = event

    order_bars: dict[int, int] = {}
    for order_id in order_ids:
        for event in index.by_order_id.get(order_id, ()):
            if event.event_type is ExplainEventType.ORDER_CREATED and event.bar_index is not None:
                order_bars[order_id] = event.bar_index
            if _event_belongs_to_trade(event, trade_id, order_ids):
                seen[event.seq] = event

    for _order_id, bar_index in order_bars.items():
        for event in index.events:
            if (
                event.event_type is ExplainEventType.SIGNAL_GENERATED
                and event.bar_index == bar_index
                and event.seq not in seen
            ):
                seen[event.seq] = event

    return tuple(sorted(seen.values(), key=lambda item: (item.timestamp_ms, item.seq)))


def _event_belongs_to_trade(event: ExplainEvent, trade_id: int, order_ids: tuple[int, ...]) -> bool:
    if event.trade_id == trade_id:
        return True
    if event.order_id is not None and event.order_id in order_ids:
        return event.event_type not in {
            ExplainEventType.PROFIT_CALCULATED,
            ExplainEventType.POSITION_CLOSED,
        } or event.trade_id in (None, trade_id)
    return False


def _build_timeline(
    events: tuple[ExplainEvent, ...], trade_id: int
) -> tuple[TradeTimelineStep, ...]:
    steps: list[TradeTimelineStep] = []
    ordered_types = (
        ExplainEventType.SIGNAL_GENERATED,
        ExplainEventType.ORDER_CREATED,
        ExplainEventType.ORDER_SUBMITTED,
        ExplainEventType.ORDER_FILLED,
        ExplainEventType.POSITION_OPENED,
        ExplainEventType.POSITION_UPDATED,
        ExplainEventType.POSITION_CLOSED,
        ExplainEventType.PROFIT_CALCULATED,
    )

    for step_type in ordered_types:
        matching = [event for event in events if event.event_type is step_type]
        if step_type is ExplainEventType.POSITION_UPDATED:
            for event in matching:
                steps.append(_step_from_event(event, trade_id, events))
            continue
        if matching:
            steps.append(_step_from_event(matching[0], trade_id, events))

    return tuple(steps)


def _step_from_event(
    event: ExplainEvent,
    trade_id: int,
    all_events: tuple[ExplainEvent, ...],
) -> TradeTimelineStep:
    related = tuple(
        other.seq
        for other in all_events
        if other.seq != event.seq
        and (
            (event.order_id is not None and other.order_id == event.order_id)
            or (event.trade_id is not None and other.trade_id == event.trade_id)
            or (event.position_id is not None and other.position_id == event.position_id)
        )
    )
    return TradeTimelineStep(
        step_type=event.event_type,
        label=_STEP_LABELS.get(event.event_type, event.event_type.value),
        event_seq=event.seq,
        timestamp_ms=event.timestamp_ms,
        bar_index=event.bar_index,
        price=event.price,
        quantity=event.quantity,
        commission=event.commission,
        slippage=event.slippage,
        cash=event.cash,
        portfolio_value=event.portfolio_value,
        reason_code=event.reason_code,
        message=event.message,
        related_event_seqs=related,
    )


def _build_summary(
    trade_id: int,
    events: tuple[ExplainEvent, ...],
    timeline: tuple[TradeTimelineStep, ...],
    order_ids: tuple[int, ...],
) -> TradeSummary:
    profit_event = next(
        (event for event in events if event.event_type is ExplainEventType.PROFIT_CALCULATED),
        None,
    )
    opened = next(
        (event for event in events if event.event_type is ExplainEventType.POSITION_OPENED),
        None,
    )
    closed = next(
        (event for event in events if event.event_type is ExplainEventType.POSITION_CLOSED),
        None,
    )

    entry_price = opened.price if opened and opened.price is not None else 0.0
    exit_price = closed.price if closed and closed.price is not None else 0.0
    entry_time = opened.timestamp_ms if opened else 0
    exit_time = closed.timestamp_ms if closed else 0
    quantity = opened.quantity if opened and opened.quantity is not None else 0.0

    gross_profit = profit_event.pnl if profit_event and profit_event.pnl is not None else 0.0
    if profit_event and profit_event.metadata.get("gross_pnl") is not None:
        gross_profit = float(profit_event.metadata["gross_pnl"])

    net_profit = gross_profit
    if profit_event and profit_event.metadata.get("net_pnl") is not None:
        net_profit = float(profit_event.metadata["net_pnl"])
    elif profit_event and profit_event.pnl is not None:
        net_profit = profit_event.pnl

    commission = profit_event.commission if profit_event and profit_event.commission else 0.0
    slippage = profit_event.slippage if profit_event and profit_event.slippage else 0.0
    mae = _optional_metric(profit_event, "mae")
    mfe = _optional_metric(profit_event, "mfe")

    direction = "long"
    if opened and opened.metadata.get("side"):
        direction = str(opened.metadata["side"])

    entry_bar = opened.bar_index if opened and opened.bar_index is not None else 0
    exit_bar = closed.bar_index if closed and closed.bar_index is not None else entry_bar
    holding_period = max(exit_bar - entry_bar, 1)

    notional = entry_price * quantity if entry_price and quantity else 0.0
    return_pct = (net_profit / notional * 100.0) if notional > 0 else 0.0

    risk_reward: float | None = None
    if mae is not None and mae < 0 and net_profit != 0:
        risk_reward = round(abs(net_profit / mae), 4)

    status = TradeOutcome.BREAK_EVEN
    if net_profit > 0:
        status = TradeOutcome.WINNING
    elif net_profit < 0:
        status = TradeOutcome.LOSING

    position_id = opened.position_id if opened else None

    return TradeSummary(
        trade_number=trade_id,
        direction=direction,
        entry_time_ms=entry_time,
        exit_time_ms=exit_time,
        entry_price=entry_price,
        exit_price=exit_price,
        gross_profit=gross_profit,
        net_profit=net_profit,
        commission=commission,
        slippage=slippage,
        holding_period_bars=holding_period,
        mae=mae,
        mfe=mfe,
        return_pct=round(return_pct, 4),
        risk_reward=risk_reward,
        status=status,
        order_ids=order_ids,
        position_id=position_id,
        event_count=len(events),
    )


def _optional_metric(event: ExplainEvent | None, key: str) -> float | None:
    if event is None:
        return None
    value = event.metadata.get(key)
    if value is None:
        return None
    return float(value)
