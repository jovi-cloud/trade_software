"""Trade inspector reconstruction tests."""

from __future__ import annotations

from app.domain.enums import OrderType, PositionSide
from app.domain.explain import ExplainEventType, ExplainLevel
from app.engine.execution.order import Order
from app.engine.execution.trade import Trade
from app.engine.explain.collector import ExplainCollector
from app.engine.explain.event_index import EventIndex
from app.engine.explain.trade_inspector import TradeOutcome, inspect_trade


def _build_round_trip_events() -> EventIndex:
    collector = ExplainCollector(ExplainLevel.TRADES_ONLY)
    collector.record_signal_generated(
        action="Buy",
        quantity=10,
        bar_index=0,
        timestamp_ms=1_000,
        accepted=True,
    )
    order = Order(
        id=1,
        order_type=OrderType.BUY_MARKET,
        quantity=10,
        submitted_bar_index=0,
        submitted_ts=1_000,
    )
    collector.record_order_created(order)
    collector.record_order_submitted(order)
    order.fill_price = 100.0
    order.fill_ts = 2_000
    order.filled_bar_index = 1
    collector.record_order_filled(order, cash=9_000.0, portfolio_value=10_000.0)
    collector.record_position_opened(
        side=PositionSide.LONG,
        quantity=10,
        price=100.0,
        bar_index=1,
        timestamp_ms=2_000,
        order_id=1,
        cash=9_000.0,
        portfolio_value=10_000.0,
    )

    close_order = Order(
        id=2,
        order_type=OrderType.CLOSE,
        quantity=10,
        submitted_bar_index=2,
        submitted_ts=3_000,
    )
    collector.record_signal_generated(
        action="Close",
        quantity=10,
        bar_index=2,
        timestamp_ms=3_000,
        accepted=True,
    )
    collector.record_order_created(close_order)
    collector.record_order_submitted(close_order)
    close_order.fill_price = 105.0
    close_order.fill_ts = 4_000
    close_order.filled_bar_index = 3
    collector.record_order_filled(close_order, cash=10_050.0, portfolio_value=10_050.0)
    collector.record_position_closed(
        side=PositionSide.LONG,
        quantity=10,
        price=105.0,
        bar_index=3,
        timestamp_ms=4_000,
        order_id=2,
        trade_seq=1,
        cash=10_050.0,
        portfolio_value=10_050.0,
    )
    trade = Trade(
        seq=1,
        side=PositionSide.LONG,
        quantity=10,
        entry_ts=2_000,
        entry_price=100.0,
        exit_ts=4_000,
        exit_price=105.0,
        gross_pnl=50.0,
        commission=0.0,
        slippage_cost=0.0,
        net_pnl=50.0,
        bars_held=2,
    )
    collector.record_profit_calculated(trade, cash=10_050.0, portfolio_value=10_050.0)
    return EventIndex.build(collector.events)


def test_inspect_trade_builds_timeline_graph() -> None:
    index = _build_round_trip_events()
    inspection = inspect_trade(index, 1)
    assert inspection is not None
    assert inspection.summary.trade_number == 1
    assert inspection.summary.status is TradeOutcome.WINNING
    assert inspection.summary.net_profit == 50.0
    step_types = [step.step_type for step in inspection.timeline]
    assert ExplainEventType.SIGNAL_GENERATED in step_types
    assert ExplainEventType.ORDER_CREATED in step_types
    assert ExplainEventType.PROFIT_CALCULATED in step_types
    assert len(inspection.event_seqs) >= 8


def test_event_index_groups_by_trade_and_order() -> None:
    index = _build_round_trip_events()
    assert 1 in index.by_trade_id
    assert 1 in index.by_order_id
    assert 2 in index.by_order_id
