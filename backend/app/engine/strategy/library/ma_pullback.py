"""Moving Average Pullback - buy the dip inside an established trend.

Where the crossover strategies enter *as* the trend turns, this one waits for the
trend to already exist and then buys weakness inside it. That makes it a
three-state machine rather than a single condition, and the state is what this
file demonstrates: a strategy may keep its own bookkeeping, as long as that
bookkeeping is about *signals* and never about cash or positions.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.domain.enums import (
    MarketType,
    ParamType,
    PositionSide,
    RiskLevel,
    StrategyCategory,
    Timeframe,
)
from app.engine.indicators.base import Indicator
from app.engine.indicators.trend import ExponentialMovingAverage, SimpleMovingAverage
from app.engine.strategy.framework import EntrySignal, ExitSignal, MarketView, StrategyBase
from app.engine.strategy.library._shared import (
    GROUP_SIGNAL,
    atr_risk,
    atr_stop_params,
    capital_pct_param,
    direction_param,
    fractional_param,
    less_than,
    max_bars_param,
    period_param,
    trailing_stop_params,
)
from app.engine.strategy.metadata import (
    ChangelogEntry,
    StrategyDocumentation,
    StrategyExample,
    StrategyMetadata,
)
from app.engine.strategy.params import ParamChoice, ParamSpec
from app.engine.strategy.risk import RiskRules

MA_EMA = "ema"
MA_SMA = "sma"


class MovingAveragePullbackStrategy(StrategyBase):
    """Buy a touch of the pullback MA inside an uptrend, once price resumes."""

    metadata = StrategyMetadata(
        id="ma_pullback",
        name="Moving Average Pullback",
        description=(
            "Waits for an established trend, for price to pull back to a shorter "
            "moving average, and then for the trend to resume before entering."
        ),
        version="1.0.0",
        author="Platform",
        category=StrategyCategory.TREND_FOLLOWING,
        markets=(MarketType.EQUITY, MarketType.INDEX, MarketType.FUTURES, MarketType.CRYPTO),
        timeframes=(Timeframe.M30, Timeframe.H1, Timeframe.H4, Timeframe.D1),
        tags=("trend", "pullback", "continuation", "moving-average"),
        risk_level=RiskLevel.MEDIUM,
        supports_long=True,
        supports_short=True,
        supports_intraday=False,
        supports_swing=True,
        supports_position_trading=True,
        documentation=StrategyDocumentation(
            overview=(
                "Trend continuation rather than trend reversal. Three things must "
                "happen in order: the long-term average must establish a direction, "
                "price must pull back to the shorter average, and price must then close "
                "back in the trend's direction. Requiring the resumption close is what "
                "separates this from catching a falling knife - a pullback that keeps "
                "going is a trend change, not an entry."
            ),
            indicators=(
                "Trend average over `trend_period` closes",
                "Pullback average over `pullback_period` closes",
            ),
            entry_rules=(
                "Uptrend requires close above the trend average, and the trend average "
                "itself rising",
                "A pullback is armed when the bar's low reaches the pullback average",
                "Long is taken on the next close back above the pullback average, "
                "within `pullback_expiry_bars` of arming",
                "Short is the mirror image",
            ),
            exit_rules=(
                "Close when price closes back through the trend average against the position",
                "ATR stop, R-multiple target and optional ATR trail can exit sooner",
            ),
            known_limitations=(
                "In a strong trend price may never reach the pullback average, so the "
                "strategy sits out exactly the moves it was designed to catch.",
                "The armed-pullback state is reset when a position opens, so it cannot "
                "queue a second entry while already in a trade - this platform models "
                "one position at a time.",
                "`pullback_expiry_bars` is a blunt instrument: a slow, orderly pullback "
                "can expire before it resolves.",
            ),
        ),
        examples=(
            StrategyExample(
                title="20/200 daily pullback, long only",
                description=(
                    "Buy pullbacks to the 20-day EMA while price is above a rising 200-day average."
                ),
                instrument="RELIANCE",
                timeframe=Timeframe.D1,
                params={
                    "pullback_period": 20,
                    "trend_period": 200,
                    "direction": "long_only",
                    "stop_atr_multiple": 2.0,
                    "target_r_multiple": 3.0,
                },
            ),
            StrategyExample(
                title="Hourly 21/100, both directions",
                description="A faster pair for swing trades on index futures.",
                instrument="NIFTY",
                timeframe=Timeframe.H1,
                params={"pullback_period": 21, "trend_period": 100, "moving_average_type": MA_EMA},
            ),
        ),
        changelog=(
            ChangelogEntry(
                version="1.0.0",
                date="2026-07-30",
                changes=(
                    "First release on the Strategy Framework.",
                    "Requires a resumption close rather than entering on the touch.",
                ),
            ),
        ),
    )

    parameters = (
        period_param(
            "pullback_period",
            description="Shorter average price pulls back to.",
            default=20,
            minimum=2,
            maximum=200,
            order=10,
            rules=less_than("trend_period"),
        ),
        period_param(
            "trend_period",
            description="Longer average that establishes the trend direction.",
            default=200,
            minimum=5,
            maximum=500,
            order=20,
        ),
        ParamSpec(
            name="moving_average_type",
            type=ParamType.CHOICE,
            description="Which average to use for both the trend and the pullback level.",
            default=MA_EMA,
            choices=(
                ParamChoice(MA_EMA, "Exponential", "Weights recent closes more heavily"),
                ParamChoice(MA_SMA, "Simple", "Weights every close in the window equally"),
            ),
            group=GROUP_SIGNAL,
            display_order=30,
        ),
        ParamSpec(
            name="pullback_expiry_bars",
            type=ParamType.INTEGER,
            description="How many bars an armed pullback stays valid before it is discarded.",
            default=5,
            minimum=1,
            maximum=100,
            step=1,
            group=GROUP_SIGNAL,
            display_order=40,
            tooltip="Short values demand a sharp resumption; long ones accept drift.",
        ),
        ParamSpec(
            name="require_rising_trend",
            type=ParamType.BOOLEAN,
            description="Require the trend average itself to be rising (falling for shorts).",
            default=True,
            group=GROUP_SIGNAL,
            display_order=50,
        ),
        direction_param(),
        capital_pct_param(),
        *atr_stop_params(stop_default=2.0, target_default=3.0),
        max_bars_param(),
        fractional_param(),
        *trailing_stop_params(),
    )

    def __init__(self, params: Mapping[str, object] | None = None) -> None:
        super().__init__(params)
        # Signal bookkeeping only: which side is armed, and on which bar.
        self._armed_side: PositionSide | None = None
        self._armed_bar_index = -1

    def declare_indicators(self) -> Mapping[str, Indicator]:
        factory = (
            ExponentialMovingAverage
            if self.params.text("moving_average_type") == MA_EMA
            else SimpleMovingAverage
        )
        return {
            "pullback_ma": factory(self.params.integer("pullback_period")),
            "trend_ma": factory(self.params.integer("trend_period")),
        }

    def declare_risk(self) -> RiskRules:
        return atr_risk(self.params)

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        trend = view.value("trend_ma")
        pullback = view.value("pullback_ma")
        if trend is None or pullback is None:
            return None

        uptrend, downtrend = self._trend_state(view, trend=trend)
        self._expire_arm(view)
        self._arm(view, pullback=pullback, uptrend=uptrend, downtrend=downtrend)

        resumed_up = self.check(
            "Resumed Above Pullback Average",
            passed=self._armed_side is PositionSide.LONG and view.bar.close > pullback,
            actual=f"armed={self._armed_label()} close {view.bar.close:.4f} vs MA {pullback:.4f}",
            expected="close back above the pullback average while armed long",
        )
        resumed_down = self.check(
            "Resumed Below Pullback Average",
            passed=self._armed_side is PositionSide.SHORT and view.bar.close < pullback,
            actual=f"armed={self._armed_label()} close {view.bar.close:.4f} vs MA {pullback:.4f}",
            expected="close back below the pullback average while armed short",
        )

        if resumed_up and uptrend:
            self._disarm()
            return EntrySignal(PositionSide.LONG, "Pullback to the moving average resumed upward")
        if resumed_down and downtrend:
            self._disarm()
            return EntrySignal(
                PositionSide.SHORT, "Pullback to the moving average resumed downward"
            )
        return None

    def exit_signal(self, view: MarketView) -> ExitSignal | None:
        position = view.position
        trend = view.value("trend_ma")
        if position is None or trend is None:
            return None
        # A position exists, so any armed pullback is stale: this platform holds
        # one position at a time and a queued second entry could never fill.
        self._disarm()
        is_long = getattr(position, "side", "") == PositionSide.LONG.value

        broke = self.check(
            "Closed Through Trend Average Against Position",
            passed=(view.bar.close < trend) if is_long else (view.bar.close > trend),
            actual=f"close {view.bar.close:.4f} vs trend {trend:.4f}",
            expected="close through the trend average against the position",
        )
        return ExitSignal("Price closed through the trend average") if broke else None

    def _trend_state(self, view: MarketView, *, trend: float) -> tuple[bool, bool]:
        close = view.bar.close
        needs_slope = self.params.flag("require_rising_trend")
        rising = view.rising("trend_ma") if needs_slope else True
        falling = view.falling("trend_ma") if needs_slope else True

        uptrend = self.check(
            "Uptrend Established",
            passed=close > trend and rising,
            actual=f"close {close:.4f} vs trend {trend:.4f}, rising={rising}",
            expected="close above a rising trend average",
        )
        downtrend = self.check(
            "Downtrend Established",
            passed=close < trend and falling,
            actual=f"close {close:.4f} vs trend {trend:.4f}, falling={falling}",
            expected="close below a falling trend average",
        )
        return uptrend, downtrend

    def _arm(self, view: MarketView, *, pullback: float, uptrend: bool, downtrend: bool) -> None:
        """Arm on a touch of the pullback average, in the trend's direction."""
        touched_from_above = uptrend and view.bar.low <= pullback
        touched_from_below = downtrend and view.bar.high >= pullback
        self.check(
            "Pulled Back To Moving Average",
            passed=touched_from_above or touched_from_below,
            actual=f"bar {view.bar.low:.4f}-{view.bar.high:.4f} vs MA {pullback:.4f}",
            expected="bar range reached the pullback average",
        )
        if touched_from_above:
            self._armed_side = PositionSide.LONG
            self._armed_bar_index = view.bar_index
        elif touched_from_below:
            self._armed_side = PositionSide.SHORT
            self._armed_bar_index = view.bar_index

    def _expire_arm(self, view: MarketView) -> None:
        if self._armed_side is None:
            return
        age = view.bar_index - self._armed_bar_index
        if age > self.params.integer("pullback_expiry_bars"):
            self._disarm()

    def _disarm(self) -> None:
        self._armed_side = None
        self._armed_bar_index = -1

    def _armed_label(self) -> str:
        return "none" if self._armed_side is None else self._armed_side.value
