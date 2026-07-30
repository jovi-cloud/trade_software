"""``StrategyBase`` orchestration, driven through the real execution engine.

These tests run strategies rather than calling hooks directly: the whole point of
the framework is that a declared strategy produces the right orders through the
untouched engine, and only an end-to-end run proves that.
"""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from app.domain.enums import ParamType, PositionSide
from app.domain.explain import ExplainLevel
from app.engine.bars import Bar, BarIterator
from app.engine.indicators.base import Indicator
from app.engine.indicators.trend import SimpleMovingAverage
from app.engine.indicators.volatility import BollingerBands
from app.engine.results.result import ExecutionResult
from app.engine.runner import ExecutionConfig, ExecutionEngine
from app.engine.strategy.framework import (
    DIRECTION_LONG_ONLY,
    DIRECTION_PARAM,
    SESSION_TIMEZONE_PARAM,
    EntrySignal,
    ExitSignal,
    MarketView,
    StrategyBase,
    default_parameter_values,
)
from app.engine.strategy.params import ParamChoice, ParamSpec
from app.engine.strategy.provider import LibraryStrategyProvider
from app.engine.strategy.risk import FixedQuantity, PercentDistance, PercentOfEquity, RiskRules
from tests.unit.engine.strategy.conftest import bars_from_closes, bars_from_ohlc, make_metadata


def run(
    strategy_class: type[StrategyBase],
    bars: list[Bar],
    params: Mapping[str, object] | None = None,
    *,
    initial_capital: float = 100_000.0,
) -> ExecutionResult:
    return ExecutionEngine(
        ExecutionConfig(initial_capital=initial_capital, explain_level=ExplainLevel.FULL)
    ).run(
        bars=BarIterator(bars),
        strategy=LibraryStrategyProvider(strategy_class, params),
    )


def conditions_by_name(result: ExecutionResult) -> dict[str, list[bool]]:
    """Every traced condition, grouped by name, in bar order."""
    collected: dict[str, list[bool]] = {}
    for event in result.explain_events:
        raw = event.metadata.get("conditions")
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, dict):
                collected.setdefault(str(item["name"]), []).append(bool(item["passed"]))
    return collected


def traced_indicators(result: ExecutionResult) -> set[str]:
    names: set[str] = set()
    for event in result.explain_events:
        raw = event.metadata.get("indicators")
        if isinstance(raw, dict):
            names.update(str(key) for key in raw)
    return names


# -- test strategies -------------------------------------------------------


class AlwaysLong(StrategyBase):
    """Enters long on the first eligible bar and never exits by rule."""

    metadata = make_metadata(id="always_long", name="Always Long")
    parameters = (
        ParamSpec(
            name="quantity",
            type=ParamType.INTEGER,
            description="Units per trade.",
            default=1,
            minimum=1,
            maximum=100,
            step=1,
        ),
    )

    def declare_risk(self) -> RiskRules:
        return RiskRules(sizing=FixedQuantity(float(self.params.integer("quantity"))))

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        return EntrySignal(PositionSide.LONG, "always")


class SmaCross(StrategyBase):
    metadata = make_metadata(id="sma_cross", name="SMA Cross")
    parameters = (
        ParamSpec(
            name="fast",
            type=ParamType.INTEGER,
            description="Fast period.",
            default=2,
            minimum=1,
            maximum=50,
            step=1,
        ),
        ParamSpec(
            name="slow",
            type=ParamType.INTEGER,
            description="Slow period.",
            default=4,
            minimum=2,
            maximum=100,
            step=1,
        ),
    )

    def declare_indicators(self) -> Mapping[str, Indicator]:
        return {
            "fast": SimpleMovingAverage(self.params.integer("fast")),
            "slow": SimpleMovingAverage(self.params.integer("slow")),
        }

    def declare_risk(self) -> RiskRules:
        return RiskRules(sizing=FixedQuantity(1.0))

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        up = self.check("Fast Above Slow", passed=view.crossed_above("fast", "slow"))
        down = self.check("Fast Below Slow", passed=view.crossed_below("fast", "slow"))
        if up:
            return EntrySignal(PositionSide.LONG, "cross up")
        if down:
            return EntrySignal(PositionSide.SHORT, "cross down")
        return None

    def exit_signal(self, view: MarketView) -> ExitSignal | None:
        return None


class ShortOnly(StrategyBase):
    metadata = make_metadata(
        id="short_only", name="Short Only", supports_long=False, supports_short=True
    )

    def declare_risk(self) -> RiskRules:
        return RiskRules(sizing=FixedQuantity(1.0))

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        # Deliberately asks for a long the metadata forbids.
        return EntrySignal(PositionSide.LONG, "asks for a forbidden long")


class Directional(StrategyBase):
    metadata = make_metadata(id="directional", name="Directional")
    parameters = (
        ParamSpec(
            name=DIRECTION_PARAM,
            type=ParamType.CHOICE,
            description="Allowed sides.",
            default="both",
            choices=(
                ParamChoice("both", "Both"),
                ParamChoice(DIRECTION_LONG_ONLY, "Long only"),
            ),
        ),
    )

    def declare_risk(self) -> RiskRules:
        return RiskRules(sizing=FixedQuantity(1.0))

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        return EntrySignal(PositionSide.SHORT, "short")


class MultiOutput(StrategyBase):
    metadata = make_metadata(id="multi_output", name="Multi Output")

    def declare_indicators(self) -> Mapping[str, Indicator]:
        return {"bb": BollingerBands(3, 2.0)}

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        self.check("Upper Readable", passed=view.value("bb", "upper") is not None)
        self.check("Primary Is Middle", passed=view.value("bb") == view.value("bb", "middle"))
        return None


class StoppedLong(StrategyBase):
    metadata = make_metadata(id="stopped_long", name="Stopped Long")

    def declare_risk(self) -> RiskRules:
        return RiskRules(sizing=FixedQuantity(1.0), stop_loss=PercentDistance(2.0))

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        return EntrySignal(PositionSide.LONG, "long")


class SessionAware(StrategyBase):
    metadata = make_metadata(id="session_aware", name="Session Aware", supports_intraday=True)
    parameters = (
        ParamSpec(
            name=SESSION_TIMEZONE_PARAM,
            type=ParamType.CHOICE,
            description="Exchange timezone.",
            default="Asia/Kolkata",
            choices=(ParamChoice("Asia/Kolkata", "India"), ParamChoice("UTC", "UTC")),
        ),
    )

    def declare_risk(self) -> RiskRules:
        return RiskRules(sizing=FixedQuantity(1.0), exit_at_time="23:59")

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        assert view.session is not None
        self.check("Has Session", passed=True, actual=view.session.local_time)
        return None


# -- warmup ----------------------------------------------------------------


def test_warmup_is_the_longest_declared_indicator():
    strategy = SmaCross({"fast": 3, "slow": 10})
    strategy.ctx = None  # type: ignore[assignment]
    strategy._indicators = dict(strategy.declare_indicators())
    strategy._risk = strategy.declare_risk()
    assert max(i.warmup_bars for i in strategy._indicators.values()) == 10


def test_no_orders_are_submitted_while_warming_up():
    result = run(SmaCross, bars_from_closes([1.0, 2.0, 3.0]), {"fast": 2, "slow": 4})
    assert result.orders == ()
    traced = conditions_by_name(result)
    assert traced["Warmup Complete"] == [False, False, False]


def test_warmup_completes_and_then_conditions_are_evaluated():
    result = run(
        SmaCross,
        bars_from_closes([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]),
        {"fast": 2, "slow": 4},
    )
    traced = conditions_by_name(result)
    assert traced["Warmup Complete"][-1] is True
    assert "Fast Above Slow" in traced


# -- entry, exit and sizing ------------------------------------------------


def test_a_long_signal_produces_a_buy_filled_at_the_next_bar_open():
    bars = bars_from_ohlc([(10, 10, 10, 10), (20, 20, 20, 20), (20, 20, 20, 20)])
    result = run(AlwaysLong, bars, {"quantity": 2})
    assert result.completed
    assert next(order.order_type.value for order in result.orders) == "buy_market"
    filled = result.orders[0]
    assert filled.quantity == pytest.approx(2.0)
    # Signal on bar 0, fill at bar 1's open of 20 - never on the signal bar.
    assert filled.fill_price == pytest.approx(20.0)


def test_percent_of_equity_sizing_uses_available_cash():
    bars = bars_from_closes([100.0, 100.0, 100.0])

    class Sized(AlwaysLong):
        metadata = make_metadata(id="sized", name="Sized")

        def declare_risk(self) -> RiskRules:
            return RiskRules(sizing=PercentOfEquity(20.0))

    result = run(Sized, bars, initial_capital=10_000.0)
    # 20% of 10,000 at price 100 is 20 units.
    assert result.orders[0].quantity == pytest.approx(20.0)


def test_an_entry_is_skipped_when_the_size_rounds_down_to_nothing():
    class TooExpensive(AlwaysLong):
        metadata = make_metadata(id="too_expensive", name="Too Expensive")

        def declare_risk(self) -> RiskRules:
            return RiskRules(sizing=PercentOfEquity(1.0))

    result = run(TooExpensive, bars_from_closes([5_000.0] * 3), initial_capital=1_000.0)
    assert result.orders == ()
    assert conditions_by_name(result)["Position Size Available"][-1] is False


def test_a_direction_the_metadata_forbids_is_refused_and_traced():
    result = run(ShortOnly, bars_from_closes([10.0, 10.0, 10.0]))
    assert result.orders == ()
    assert conditions_by_name(result)["Direction Permitted"][-1] is False


def test_the_direction_parameter_narrows_what_the_metadata_allows():
    bars = bars_from_closes([10.0, 10.0, 10.0])
    both = run(Directional, bars, {DIRECTION_PARAM: "both"})
    assert next(order.order_type.value for order in both.orders) == "sell_market"

    long_only = run(Directional, bars, {DIRECTION_PARAM: DIRECTION_LONG_ONLY})
    assert long_only.orders == ()


def test_a_declared_stop_closes_the_position_and_logs_the_reason():
    # Enter at bar 1's open of 100; bar 2 trades down through the 2% stop at 98.
    bars = bars_from_ohlc(
        [(100, 100, 100, 100), (100, 101, 100, 100), (100, 100, 95, 96), (96, 96, 96, 96)]
    )
    result = run(StoppedLong, bars)
    order_types = [order.order_type.value for order in result.orders]
    assert "close" in order_types
    assert any("stop_loss" in entry for entry in result.strategy_logs)
    assert conditions_by_name(result)["Risk Exit Triggered"][-1] is True


def test_a_strategy_with_no_exit_signal_still_traces_the_exit_check():
    bars = bars_from_ohlc([(10, 10, 10, 10)] * 4)
    result = run(AlwaysLong, bars)
    assert conditions_by_name(result)["Exit Rules Met"][-1] is False


# -- market view -----------------------------------------------------------


def test_multi_output_indicators_are_addressable_by_output_and_by_primary():
    result = run(MultiOutput, bars_from_closes([1.0, 2.0, 3.0, 4.0, 5.0]))
    traced = conditions_by_name(result)
    assert traced["Upper Readable"][-1] is True
    assert traced["Primary Is Middle"][-1] is True


def test_indicator_values_are_published_for_the_bar_inspector():
    result = run(MultiOutput, bars_from_closes([1.0, 2.0, 3.0, 4.0, 5.0]))
    names = traced_indicators(result)
    assert "bb" in names
    assert "bb.upper" in names
    assert "bb.percent_b" in names


def test_crossover_helpers_need_both_bars_to_have_values():
    view = MarketView(
        bar=bars_from_closes([1.0])[0],
        bar_index=0,
        current={"a": 2.0, "b": 1.0},
        previous={},
        position=None,
        bars_held=0,
        session=None,
    )
    assert view.crossed_above("a", "b") is False
    assert view.rising("a") is False


def test_crossover_helpers_detect_a_cross_and_ignore_a_mere_gap():
    crossed = MarketView(
        bar=bars_from_closes([1.0])[0],
        bar_index=1,
        current={"a": 2.0, "b": 1.0},
        previous={"a": 1.0, "b": 1.0},
        position=None,
        bars_held=0,
        session=None,
    )
    assert crossed.crossed_above("a", "b") is True
    assert crossed.crossed_below("a", "b") is False

    already_above = MarketView(
        bar=bars_from_closes([1.0])[0],
        bar_index=2,
        current={"a": 3.0, "b": 1.0},
        previous={"a": 2.0, "b": 1.0},
        position=None,
        bars_held=0,
        session=None,
    )
    assert already_above.crossed_above("a", "b") is False


def test_level_crossing_helpers():
    view = MarketView(
        bar=bars_from_closes([1.0])[0],
        bar_index=1,
        current={"rsi": 25.0},
        previous={"rsi": 35.0},
        position=None,
        bars_held=0,
        session=None,
    )
    assert view.crossed_level_below("rsi", 30.0) is True
    assert view.crossed_level_above("rsi", 30.0) is False
    assert view.falling("rsi") is True


def test_require_fails_loudly_on_a_value_that_has_not_warmed_up():
    view = MarketView(
        bar=bars_from_closes([1.0])[0],
        bar_index=0,
        current={"a": None},
        previous={},
        position=None,
        bars_held=0,
        session=None,
    )
    with pytest.raises(ValueError, match="has no value on bar 0"):
        view.require("a")


def test_has_reports_whether_named_outputs_are_available():
    view = MarketView(
        bar=bars_from_closes([1.0])[0],
        bar_index=0,
        current={"a": 1.0, "b": None},
        previous={},
        position=None,
        bars_held=0,
        session=None,
    )
    assert view.has("a") is True
    assert view.has("a", "b") is False


# -- session and misc ------------------------------------------------------


def test_a_session_snapshot_is_available_when_a_time_rule_is_declared():
    result = run(SessionAware, bars_from_closes([10.0, 10.0, 10.0]))
    assert result.completed
    assert conditions_by_name(result)["Has Session"][-1] is True


def test_session_timezone_defaults_to_utc_without_the_parameter():
    assert AlwaysLong().session_timezone == "UTC"
    assert SessionAware().session_timezone == "Asia/Kolkata"


def test_default_parameter_values_reads_the_class_declaration():
    assert default_parameter_values(SmaCross) == {"fast": 2, "slow": 4}


def test_entry_rules_are_not_evaluated_while_a_position_is_open():
    # `AlwaysLong` would ask to buy on every bar. The framework routes an open
    # position to the exit path instead, so the order service never sees a
    # duplicate buy to reject - the guardrail is never reached because the
    # framework does not get that far.
    result = run(AlwaysLong, bars_from_closes([10.0] * 5))
    buys = [order for order in result.orders if order.order_type.value == "buy_market"]
    assert len(buys) == 1
    assert not any("already open" in warning for warning in result.warnings)

    traced = conditions_by_name(result)
    # Once in the trade, only the exit-side conditions are traced.
    assert traced["Exit Rules Met"]
    assert len(traced["Entry Rules Met"]) < len(traced["Warmup Complete"])
