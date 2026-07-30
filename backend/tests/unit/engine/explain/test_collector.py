"""ExplainCollector unit tests."""

from __future__ import annotations

from app.domain.conditions import ConditionSnapshot
from app.domain.enums import OrderType, PositionSide
from app.domain.explain import ExplainEventStatus, ExplainEventType, ExplainLayer, ExplainLevel
from app.engine.execution.order import Order
from app.engine.explain.collector import MAX_PER_BAR_EXPLAIN_EVENTS, ExplainCollector
from app.engine.explain.condition_collector import ConditionCollector


def _order(
    *,
    order_id: int = 1,
    order_type: OrderType = OrderType.BUY_MARKET,
    submitted_bar_index: int = 0,
    submitted_ts: int = 1_000,
) -> Order:
    return Order(
        id=order_id,
        order_type=order_type,
        quantity=10,
        submitted_bar_index=submitted_bar_index,
        submitted_ts=submitted_ts,
    )


def test_disabled_collector_records_nothing() -> None:
    collector = ExplainCollector.disabled()
    collector.record_run_started(bar_count=100)
    assert collector.events == ()


def test_trades_only_records_lifecycle_and_trade_events() -> None:
    collector = ExplainCollector(ExplainLevel.TRADES_ONLY)
    collector.record_run_started(bar_count=3)
    collector.record_strategy_loaded()
    collector.record_signal_generated(
        action="Buy",
        quantity=10,
        bar_index=0,
        timestamp_ms=1_000,
        accepted=True,
    )
    order = _order()
    collector.record_order_submitted(order)
    order.fill_price = 100.5
    order.fill_ts = 2_000
    order.filled_bar_index = 1
    collector.record_order_filled(order, cash=9_000.0, portfolio_value=10_000.0)
    collector.record_position_opened(
        side=PositionSide.LONG,
        quantity=10,
        price=100.5,
        bar_index=1,
        timestamp_ms=2_000,
        order_id=1,
        cash=9_000.0,
        portfolio_value=10_000.0,
    )
    collector.record_run_completed(completed=True, trade_count=0)

    types = {event.event_type for event in collector.events}
    assert ExplainEventType.RUN_STARTED in types
    assert ExplainEventType.ORDER_SUBMITTED in types
    assert ExplainEventType.ORDER_FILLED in types
    assert ExplainEventType.POSITION_OPENED in types
    assert ExplainEventType.RUN_COMPLETED in types
    assert ExplainEventType.BAR_PROCESSING_STARTED not in types


def test_full_level_records_bar_processing() -> None:
    collector = ExplainCollector(ExplainLevel.FULL)
    collector.record_bar_processing_started(bar_index=0, timestamp_ms=1_000)
    assert len(collector.events) == 1
    assert collector.events[0].event_type is ExplainEventType.BAR_PROCESSING_STARTED


def test_rejected_signals_omitted_in_trades_only() -> None:
    collector = ExplainCollector(ExplainLevel.TRADES_ONLY)
    collector.record_signal_generated(
        action="Buy",
        quantity=10,
        bar_index=0,
        timestamp_ms=1_000,
        accepted=False,
        rejection_reason="no open position",
    )
    assert collector.events == ()


def test_narrative_layer_events_emitted_on_fills() -> None:
    collector = ExplainCollector(ExplainLevel.TRADES_ONLY)
    order = _order()
    collector.record_order_submitted(order)
    order.fill_price = 100.0
    order.fill_ts = 2_000
    order.filled_bar_index = 1
    collector.record_order_filled(order, cash=9_000.0, portfolio_value=10_000.0)

    narrative = [event for event in collector.events if event.layer is ExplainLayer.NARRATIVE]
    assert len(narrative) >= 2
    assert all(event.event_type is ExplainEventType.HUMAN_NARRATIVE for event in narrative)


def test_events_have_sequential_seq_and_human_messages() -> None:
    collector = ExplainCollector(ExplainLevel.TRADES_ONLY)
    collector.record_run_started(bar_count=1)
    collector.record_strategy_loaded()
    assert collector.events[0].seq == 1
    assert collector.events[1].seq == 2
    assert collector.events[0].message
    assert collector.events[0].status is ExplainEventStatus.INFO


def _conditions(bar_index: int) -> ConditionSnapshot:
    collector = ConditionCollector()
    collector.trace_condition("EMA20 > EMA50", actual="1 > 0", expected="True", passed=True)
    return collector.snapshot(bar_index=bar_index)


def test_conditions_are_decision_detail_and_need_full_level() -> None:
    collector = ExplainCollector(ExplainLevel.TRADES_ONLY)
    collector.record_conditions_evaluated(_conditions(0), timestamp_ms=1_000)
    assert collector.events == ()


def test_per_bar_events_stop_at_the_budget_and_are_counted() -> None:
    collector = ExplainCollector(ExplainLevel.FULL)
    for bar_index in range(MAX_PER_BAR_EXPLAIN_EVENTS + 250):
        collector.record_conditions_evaluated(_conditions(bar_index), timestamp_ms=bar_index)

    assert len(collector.events) == MAX_PER_BAR_EXPLAIN_EVENTS
    assert collector.dropped_event_count == 250


def test_the_budget_never_costs_a_trade_event() -> None:
    """Exhausting the per-bar budget must not silence the trade record."""
    collector = ExplainCollector(ExplainLevel.FULL)
    for bar_index in range(MAX_PER_BAR_EXPLAIN_EVENTS + 1):
        collector.record_conditions_evaluated(_conditions(bar_index), timestamp_ms=bar_index)
    assert collector.dropped_event_count == 1

    order = _order()
    collector.record_order_submitted(order)
    order.fill_price = 100.0
    order.fill_ts = 2_000
    order.filled_bar_index = 1
    collector.record_order_filled(order, cash=9_000.0, portfolio_value=10_000.0)
    collector.record_run_completed(completed=True, trade_count=1)

    types = {event.event_type for event in collector.events[MAX_PER_BAR_EXPLAIN_EVENTS:]}
    assert ExplainEventType.ORDER_SUBMITTED in types
    assert ExplainEventType.ORDER_FILLED in types
    assert ExplainEventType.RUN_COMPLETED in types
