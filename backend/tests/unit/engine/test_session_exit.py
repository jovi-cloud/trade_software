"""Tests for run-level session exit at a fixed exchange-local time."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.domain.enums import PositionSide
from app.domain.explain import ExplainLevel
from app.engine.bars import Bar, BarIterator
from app.engine.indicators.session import SessionClock
from app.engine.runner import ExecutionConfig, ExecutionEngine
from app.engine.strategy.framework import EntrySignal, MarketView, StrategyBase
from app.engine.strategy.provider import LibraryStrategyProvider
from app.engine.strategy.risk import (
    FixedQuantity,
    PercentDistance,
    RiskRules,
    TradeRiskState,
    apply_session_exit_override,
    evaluate_risk_exit,
)
from tests.unit.engine.strategy.conftest import make_metadata


def test_apply_session_exit_override_replaces_strategy_exit_time() -> None:
    rules = RiskRules(exit_at_time="15:30")
    updated = apply_session_exit_override(rules, "14:55")
    assert updated.exit_at_time == "14:55"


def test_session_exit_fires_on_1455_candle_ist() -> None:
    zone = ZoneInfo("Asia/Kolkata")
    rules = RiskRules(exit_at_time="14:55")
    state = TradeRiskState.open(
        side=PositionSide.LONG,
        entry_price=100.0,
        entry_bar_index=0,
        atr=None,
        rules=rules,
    )
    clock = SessionClock("Asia/Kolkata")

    def bar_at(hour: int, minute: int) -> Bar:
        moment = datetime(2024, 3, 1, hour, minute, tzinfo=zone)
        return Bar(
            ts=int(moment.timestamp() * 1000),
            open=100.0,
            high=100.5,
            low=99.5,
            close=100.0,
            volume=1.0,
        )

    before = bar_at(14, 54)
    clock.advance(before)
    assert (
        evaluate_risk_exit(state, bar=before, bars_held=1, rules=rules, atr=None, clock=clock)
        is None
    )

    at_exit = bar_at(14, 55)
    clock.advance(at_exit)
    exit_ = evaluate_risk_exit(
        state, bar=at_exit, bars_held=2, rules=rules, atr=None, clock=clock
    )
    assert exit_ is not None
    assert exit_.code == "session_exit"


def test_stop_loss_takes_precedence_over_session_exit() -> None:
    zone = ZoneInfo("Asia/Kolkata")
    rules = RiskRules(stop_loss=PercentDistance(1.0), exit_at_time="14:55")
    state = TradeRiskState.open(
        side=PositionSide.LONG,
        entry_price=100.0,
        entry_bar_index=0,
        atr=None,
        rules=rules,
    )
    clock = SessionClock("Asia/Kolkata")
    moment = datetime(2024, 3, 1, 14, 55, tzinfo=zone)
    bar = Bar(
        ts=int(moment.timestamp() * 1000),
        open=99.0,
        high=100.0,
        low=98.0,
        close=98.5,
        volume=1.0,
    )
    clock.advance(bar)
    exit_ = evaluate_risk_exit(state, bar=bar, bars_held=2, rules=rules, atr=None, clock=clock)
    assert exit_ is not None
    assert exit_.code == "stop_loss"


class HoldWithoutStops(StrategyBase):
    metadata = make_metadata(id="hold_without_stops", name="Hold Without Stops")

    def declare_risk(self) -> RiskRules:
        return RiskRules(sizing=FixedQuantity(1.0))

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        if view.bar_index == 1:
            return EntrySignal(PositionSide.LONG, "enter once")
        return None


def test_engine_flattens_at_session_exit_time() -> None:
    zone = ZoneInfo("Asia/Kolkata")

    def ist_bar(hour: int, minute: int, close: float) -> Bar:
        moment = datetime(2024, 3, 1, hour, minute, tzinfo=zone)
        return Bar(
            ts=int(moment.timestamp() * 1000),
            open=close,
            high=close + 0.5,
            low=close - 0.5,
            close=close,
            volume=1.0,
        )

    bars = [
        ist_bar(9, 15, 100.0),
        ist_bar(10, 0, 101.0),
        ist_bar(14, 54, 102.0),
        ist_bar(14, 55, 102.0),
        ist_bar(15, 0, 101.0),
    ]
    result = ExecutionEngine(
        ExecutionConfig(
            initial_capital=100_000.0,
            explain_level=ExplainLevel.NONE,
            session_timezone="Asia/Kolkata",
            session_exit_at="14:55",
        )
    ).run(
        bars=BarIterator(bars),
        strategy=LibraryStrategyProvider(HoldWithoutStops, {}),
    )
    assert result.completed
    assert result.trade_count == 1
    assert result.trades[0].exit_reason == "session_exit"
