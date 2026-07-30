"""Risk rules: sizing arithmetic and protective-exit evaluation."""

from __future__ import annotations

import pytest

from app.domain.enums import PositionSide
from app.engine.indicators.session import SessionClock
from app.engine.strategy.risk import (
    AtrDistance,
    FixedNotional,
    FixedQuantity,
    PercentDistance,
    PercentOfEquity,
    RiskPerTrade,
    RiskRules,
    RMultipleDistance,
    TradeRiskState,
    evaluate_risk_exit,
)
from tests.unit.engine.strategy.conftest import bars_from_ohlc

# -- sizing ----------------------------------------------------------------


def test_fixed_quantity_ignores_capital_and_price():
    rule = FixedQuantity(3.0)
    assert rule.quantity(capital=1_000, price=50, stop_distance=None) == pytest.approx(3.0)
    assert rule.quantity(capital=10, price=5_000, stop_distance=None) == pytest.approx(3.0)


def test_fixed_notional_divides_the_amount_by_price():
    rule = FixedNotional(1_000.0)
    assert rule.quantity(capital=10_000, price=250, stop_distance=None) == pytest.approx(4.0)


def test_fixed_notional_never_exceeds_available_capital():
    rule = FixedNotional(10_000.0)
    assert rule.quantity(capital=500, price=100, stop_distance=None) == pytest.approx(5.0)


def test_percent_of_equity_deploys_the_declared_share():
    rule = PercentOfEquity(20.0)
    # 20% of 100,000 is 20,000; at 250 that is 80 units.
    assert rule.quantity(capital=100_000, price=250, stop_distance=None) == pytest.approx(80.0)


def test_percent_of_equity_returns_zero_without_capital_or_price():
    rule = PercentOfEquity(20.0)
    assert rule.quantity(capital=0, price=100, stop_distance=None) == 0.0
    assert rule.quantity(capital=100, price=0, stop_distance=None) == 0.0


def test_risk_per_trade_sizes_from_the_stop_distance():
    rule = RiskPerTrade(1.0)
    # Risking 1% of 100,000 = 1,000; a stop 5 away means 200 units.
    assert rule.quantity(capital=100_000, price=100, stop_distance=5.0) == pytest.approx(200.0)


def test_risk_per_trade_is_capped_by_what_the_account_can_pay_for():
    rule = RiskPerTrade(1.0)
    # A very tight stop implies 10,000 units, which 100,000 at price 100 cannot buy.
    quantity = rule.quantity(capital=100_000, price=100, stop_distance=0.1)
    assert quantity == pytest.approx(1_000.0)


def test_risk_per_trade_reports_zero_without_a_stop():
    rule = RiskPerTrade(1.0)
    assert rule.quantity(capital=100_000, price=100, stop_distance=None) == 0.0
    assert rule.quantity(capital=100_000, price=100, stop_distance=0.0) == 0.0


def test_resolve_quantity_floors_to_whole_units_by_default():
    rules = RiskRules(sizing=PercentOfEquity(10.0))
    # 10% of 1,000 is 100; at 30 that is 3.33 units -> 3.
    assert rules.resolve_quantity(capital=1_000, price=30, atr=None) == pytest.approx(3.0)


def test_resolve_quantity_keeps_fractions_when_declared():
    rules = RiskRules(sizing=PercentOfEquity(10.0), fractional_quantity=True)
    assert rules.resolve_quantity(capital=1_000, price=30, atr=None) == pytest.approx(3.333333)


def test_resolve_quantity_is_zero_when_the_account_cannot_afford_one_unit():
    rules = RiskRules(sizing=PercentOfEquity(1.0))
    assert rules.resolve_quantity(capital=100, price=500, atr=None) == 0.0


# -- level rules -----------------------------------------------------------


def test_percent_distance_scales_with_the_entry_price():
    assert PercentDistance(2.0).distance(entry_price=100, atr=None) == pytest.approx(2.0)
    assert PercentDistance(2.0).distance(entry_price=500, atr=None) == pytest.approx(10.0)


def test_atr_distance_scales_with_volatility():
    assert AtrDistance(2.0).distance(entry_price=100, atr=3.0) == pytest.approx(6.0)


def test_atr_distance_is_unavailable_without_an_atr_reading():
    assert AtrDistance(2.0).distance(entry_price=100, atr=None) is None
    assert AtrDistance(2.0).distance(entry_price=100, atr=0.0) is None


def test_r_multiple_target_is_resolved_from_the_stop_distance():
    rules = RiskRules(stop_loss=PercentDistance(1.0), take_profit=RMultipleDistance(3.0))
    assert rules.stop_distance(entry_price=100, atr=None) == pytest.approx(1.0)
    assert rules.target_distance(entry_price=100, atr=None) == pytest.approx(3.0)


def test_r_multiple_target_is_unavailable_without_a_stop():
    rules = RiskRules(take_profit=RMultipleDistance(3.0))
    assert rules.target_distance(entry_price=100, atr=None) is None


def test_needs_atr_only_when_a_rule_is_atr_based():
    assert RiskRules(stop_loss=PercentDistance(1.0)).needs_atr is False
    assert RiskRules(stop_loss=AtrDistance(2.0)).needs_atr is True
    assert RiskRules(trailing_stop=AtrDistance(2.0)).needs_atr is True


def test_needs_session_clock_only_when_a_time_rule_is_declared():
    assert RiskRules().needs_session_clock is False
    assert RiskRules(exit_at_time="15:15").needs_session_clock is True
    assert RiskRules(no_entry_after="14:30").needs_session_clock is True


def test_describe_lists_every_declared_rule():
    rules = RiskRules(
        sizing=PercentOfEquity(20.0),
        stop_loss=AtrDistance(2.0),
        take_profit=RMultipleDistance(3.0),
        trailing_stop=PercentDistance(1.5),
        max_bars_in_trade=30,
        exit_at_time="15:15",
        no_entry_after="14:30",
    )
    text = " | ".join(rules.describe())
    assert "20% of available capital" in text
    assert "2x ATR" in text
    assert "3R" in text
    assert "best price reached" in text
    assert "after 30 bars" in text
    assert "15:15" in text
    assert "14:30" in text
    assert "whole units" in text


# -- trade state -----------------------------------------------------------


def test_opening_a_long_places_the_stop_below_and_target_above_entry():
    rules = RiskRules(stop_loss=PercentDistance(2.0), take_profit=PercentDistance(4.0))
    state = TradeRiskState.open(
        side=PositionSide.LONG, entry_price=100.0, entry_bar_index=0, atr=None, rules=rules
    )
    assert state.stop_level == pytest.approx(98.0)
    assert state.target_level == pytest.approx(104.0)


def test_opening_a_short_mirrors_the_levels():
    rules = RiskRules(stop_loss=PercentDistance(2.0), take_profit=PercentDistance(4.0))
    state = TradeRiskState.open(
        side=PositionSide.SHORT, entry_price=100.0, entry_bar_index=0, atr=None, rules=rules
    )
    assert state.stop_level == pytest.approx(102.0)
    assert state.target_level == pytest.approx(96.0)


def test_a_trade_with_no_rules_has_no_levels():
    state = TradeRiskState.open(
        side=PositionSide.LONG, entry_price=100.0, entry_bar_index=0, atr=None, rules=RiskRules()
    )
    assert state.stop_level is None
    assert state.target_level is None


def test_best_price_tracks_the_favourable_extreme():
    state = TradeRiskState.open(
        side=PositionSide.LONG, entry_price=100.0, entry_bar_index=0, atr=None, rules=RiskRules()
    )
    for one in bars_from_ohlc([(100, 105, 99, 104), (104, 103, 100, 101)]):
        state.observe(one)
    assert state.best_price == pytest.approx(105.0)


def test_best_price_for_a_short_tracks_the_low():
    state = TradeRiskState.open(
        side=PositionSide.SHORT, entry_price=100.0, entry_bar_index=0, atr=None, rules=RiskRules()
    )
    for one in bars_from_ohlc([(100, 101, 95, 96), (96, 99, 97, 98)]):
        state.observe(one)
    assert state.best_price == pytest.approx(95.0)


def test_trailing_level_follows_the_best_price():
    rules = RiskRules(trailing_stop=PercentDistance(10.0))
    state = TradeRiskState.open(
        side=PositionSide.LONG, entry_price=100.0, entry_bar_index=0, atr=None, rules=rules
    )
    state.observe(bars_from_ohlc([(100, 120, 100, 118)])[0])
    assert state.trailing_level(rules, None) == pytest.approx(108.0)


# -- exit evaluation -------------------------------------------------------


def long_state(
    rules: RiskRules, *, entry: float = 100.0, atr: float | None = None
) -> TradeRiskState:
    return TradeRiskState.open(
        side=PositionSide.LONG, entry_price=entry, entry_bar_index=0, atr=atr, rules=rules
    )


def test_no_exit_when_nothing_is_breached():
    rules = RiskRules(stop_loss=PercentDistance(5.0), take_profit=PercentDistance(5.0))
    state = long_state(rules)
    bar = bars_from_ohlc([(100, 102, 99, 101)])[0]
    exit_ = evaluate_risk_exit(state, bar=bar, bars_held=1, rules=rules, atr=None, clock=None)
    assert exit_ is None


def test_a_stop_fires_when_the_bar_low_reaches_the_level():
    rules = RiskRules(stop_loss=PercentDistance(2.0))
    state = long_state(rules)
    bar = bars_from_ohlc([(100, 101, 97, 99)])[0]
    exit_ = evaluate_risk_exit(state, bar=bar, bars_held=1, rules=rules, atr=None, clock=None)
    assert exit_ is not None
    assert exit_.code == "stop_loss"
    assert exit_.level == pytest.approx(98.0)


def test_a_target_fires_when_the_bar_high_reaches_the_level():
    rules = RiskRules(take_profit=PercentDistance(3.0))
    state = long_state(rules)
    bar = bars_from_ohlc([(100, 104, 100, 103)])[0]
    exit_ = evaluate_risk_exit(state, bar=bar, bars_held=1, rules=rules, atr=None, clock=None)
    assert exit_ is not None
    assert exit_.code == "take_profit"


def test_the_stop_wins_when_a_bar_spans_both_levels():
    # Bar data cannot say which was touched first; assuming the profitable one
    # is how a backtest flatters itself.
    rules = RiskRules(stop_loss=PercentDistance(2.0), take_profit=PercentDistance(2.0))
    state = long_state(rules)
    bar = bars_from_ohlc([(100, 110, 90, 100)])[0]
    exit_ = evaluate_risk_exit(state, bar=bar, bars_held=1, rules=rules, atr=None, clock=None)
    assert exit_ is not None
    assert exit_.code == "stop_loss"


def test_a_short_stop_fires_on_the_bar_high():
    rules = RiskRules(stop_loss=PercentDistance(2.0))
    state = TradeRiskState.open(
        side=PositionSide.SHORT, entry_price=100.0, entry_bar_index=0, atr=None, rules=rules
    )
    bar = bars_from_ohlc([(100, 103, 99, 102)])[0]
    exit_ = evaluate_risk_exit(state, bar=bar, bars_held=1, rules=rules, atr=None, clock=None)
    assert exit_ is not None
    assert exit_.code == "stop_loss"


def test_a_trailing_stop_fires_after_price_pulls_back_from_its_best():
    rules = RiskRules(trailing_stop=PercentDistance(10.0))
    state = long_state(rules)
    state.observe(bars_from_ohlc([(100, 120, 100, 118)])[0])  # trail now at 108
    bar = bars_from_ohlc([(118, 119, 107, 108)])[0]
    exit_ = evaluate_risk_exit(state, bar=bar, bars_held=2, rules=rules, atr=None, clock=None)
    assert exit_ is not None
    assert exit_.code == "trailing_stop"


def test_an_atr_stop_uses_the_atr_captured_at_entry():
    rules = RiskRules(stop_loss=AtrDistance(2.0))
    state = long_state(rules, atr=5.0)  # stop 10 below entry -> 90
    assert state.stop_level == pytest.approx(90.0)
    # A much smaller current ATR must not tighten the stop.
    bar = bars_from_ohlc([(100, 101, 95, 96)])[0]
    assert evaluate_risk_exit(state, bar=bar, bars_held=1, rules=rules, atr=0.5, clock=None) is None


def test_the_bar_limit_fires_at_the_declared_count():
    rules = RiskRules(max_bars_in_trade=5)
    state = long_state(rules)
    bar = bars_from_ohlc([(100, 101, 99, 100)])[0]
    exit_before = evaluate_risk_exit(state, bar=bar, bars_held=4, rules=rules, atr=None, clock=None)
    assert exit_before is None
    exit_ = evaluate_risk_exit(state, bar=bar, bars_held=5, rules=rules, atr=None, clock=None)
    assert exit_ is not None
    assert exit_.code == "max_bars"


def test_the_session_exit_fires_at_or_after_the_declared_time():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app.engine.bars import Bar

    zone = ZoneInfo("Asia/Kolkata")
    rules = RiskRules(exit_at_time="15:15")
    state = long_state(rules)
    clock = SessionClock("Asia/Kolkata")

    def bar_at(hour: int, minute: int) -> Bar:
        moment = datetime(2024, 3, 1, hour, minute, tzinfo=zone)
        return Bar(
            ts=int(moment.timestamp() * 1000), open=100, high=101, low=99, close=100, volume=1
        )

    early = bar_at(14, 0)
    clock.advance(early)
    assert (
        evaluate_risk_exit(state, bar=early, bars_held=1, rules=rules, atr=None, clock=clock)
        is None
    )

    late = bar_at(15, 20)
    clock.advance(late)
    exit_ = evaluate_risk_exit(state, bar=late, bars_held=2, rules=rules, atr=None, clock=clock)
    assert exit_ is not None
    assert exit_.code == "session_exit"
