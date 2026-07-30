"""Bar inspector reconstruction tests."""

from __future__ import annotations

from app.domain.enums import OrderType
from app.domain.explain import ExplainLevel
from app.engine.execution.order import Order
from app.engine.explain.bar_inspector import DecisionType, build_navigation, inspect_bar
from app.engine.explain.collector import ExplainCollector
from app.engine.explain.condition_collector import ConditionCollector
from app.engine.explain.event_index import EventIndex


def _candles() -> list[dict[str, float | int]]:
    return [
        {"ts": 1_000, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 1000},
        {"ts": 2_000, "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.5, "volume": 1200},
        {"ts": 3_000, "open": 101.5, "high": 103.0, "low": 101.0, "close": 102.0, "volume": 900},
    ]


def _collector_with_buy_signal() -> ExplainCollector:
    # FULL: condition traces are what the Decision Inspector reads, and only
    # FULL records them.
    collector = ExplainCollector(ExplainLevel.FULL)
    conditions = ConditionCollector()
    conditions.trace_condition(
        "EMA20 > EMA50",
        actual="101.2 > 100.8",
        expected="True",
        passed=True,
    )
    conditions.trace_indicator("RSI", 55.0)
    collector.record_conditions_evaluated(
        conditions.snapshot(bar_index=1),
        timestamp_ms=2_000,
    )
    collector.record_signal_generated(
        action="Buy",
        quantity=10,
        bar_index=1,
        timestamp_ms=2_000,
        accepted=True,
    )
    order = Order(
        id=1,
        order_type=OrderType.BUY_MARKET,
        quantity=10,
        submitted_bar_index=1,
        submitted_ts=2_000,
    )
    collector.record_order_created(order)
    collector.record_order_submitted(order)
    return collector


def test_inspect_bar_no_trade_when_flat() -> None:
    index = EventIndex.build(())
    navigation = build_navigation(bar_index=0, bar_count=3, index=index)
    inspection = inspect_bar(
        bar_index=0,
        candles=_candles(),
        orders=[],
        index=index,
        navigation=navigation,
    )
    assert inspection is not None
    assert inspection.decision.decision_type is DecisionType.NO_TRADE
    assert "No trading signal" in inspection.decision.message


def test_inspect_bar_buy_decision_with_conditions() -> None:
    index = EventIndex.build(_collector_with_buy_signal().events)
    navigation = build_navigation(bar_index=1, bar_count=3, index=index)
    inspection = inspect_bar(
        bar_index=1,
        candles=_candles(),
        orders=[
            {
                "id": 1,
                "order_type": "buy_market",
                "quantity": 10,
                "submitted_bar_index": 1,
                "submitted_ts": 2_000,
                "status": "pending",
            }
        ],
        index=index,
        navigation=navigation,
    )
    assert inspection is not None
    assert inspection.decision.decision_type is DecisionType.BUY
    assert len(inspection.conditions) == 1
    assert inspection.conditions[0].name == "EMA20 > EMA50"
    assert inspection.market_state.indicators["RSI"] == 55.0
    assert len(inspection.open_orders) == 1
    assert inspection.navigation.next_bar_index == 2


def test_build_navigation_signal_targets() -> None:
    index = EventIndex.build(_collector_with_buy_signal().events)
    navigation = build_navigation(bar_index=1, bar_count=3, index=index)
    assert navigation.first_signal_bar == 1
    assert navigation.last_signal_bar == 1
