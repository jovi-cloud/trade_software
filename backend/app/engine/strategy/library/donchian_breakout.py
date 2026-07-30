"""Donchian channel breakout - the classic Turtle-style entry."""

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
from app.engine.indicators.trend import DonchianChannel
from app.engine.strategy.framework import EntrySignal, ExitSignal, MarketView, StrategyBase
from app.engine.strategy.library._shared import (
    GROUP_SIGNAL,
    atr_risk,
    atr_stop_params,
    capital_pct_param,
    direction_param,
    fractional_param,
    max_bars_param,
    period_param,
)
from app.engine.strategy.metadata import (
    ChangelogEntry,
    StrategyDocumentation,
    StrategyExample,
    StrategyMetadata,
)
from app.engine.strategy.params import ParamSpec
from app.engine.strategy.risk import RiskRules


class DonchianBreakoutStrategy(StrategyBase):
    """Buy a close above the prior N-bar high; exit on the shorter opposite channel."""

    metadata = StrategyMetadata(
        id="donchian_breakout",
        name="Donchian Breakout",
        description=(
            "Enters on a close beyond the prior N-bar high or low and exits on a "
            "shorter opposite-channel break."
        ),
        version="1.0.0",
        author="Platform",
        category=StrategyCategory.BREAKOUT,
        markets=(MarketType.FUTURES, MarketType.INDEX, MarketType.EQUITY, MarketType.CRYPTO),
        timeframes=(Timeframe.H1, Timeframe.H4, Timeframe.D1, Timeframe.W1),
        tags=("breakout", "donchian", "turtle", "trend"),
        risk_level=RiskLevel.HIGH,
        supports_long=True,
        supports_short=True,
        supports_intraday=False,
        supports_swing=True,
        supports_position_trading=True,
        documentation=StrategyDocumentation(
            overview=(
                "The original systematic trend-following entry: if price makes a new "
                "N-period extreme, join it. The channel is computed excluding the "
                "current bar, so 'a new high' means a high above everything in the "
                "lookback rather than trivially above a channel that already contains "
                "it. The exit uses a shorter channel, which is what keeps the average "
                "winner larger than the average loser."
            ),
            indicators=(
                "Entry Donchian channel over `entry_period` bars, excluding the current bar",
                "Exit Donchian channel over `exit_period` bars, excluding the current bar",
            ),
            entry_rules=(
                "Long when the close is above the prior `entry_period`-bar high",
                "Short when the close is below the prior `entry_period`-bar low",
            ),
            exit_rules=(
                "Close a long when the close falls below the prior `exit_period`-bar low",
                "Close a short when the close rises above the prior `exit_period`-bar high",
                "ATR stop and optional ATR trail can exit sooner",
            ),
            known_limitations=(
                "Low win rate by design: most breakouts fail, and the strategy depends "
                "on a small number of large winners. Expect long drawdowns.",
                "Breakout entries are the worst case for slippage - the fill happens at "
                "the next open, after the move that triggered the signal.",
                "Needs instruments that actually trend; on mean-reverting instruments "
                "it is a losing strategy in every configuration.",
            ),
            references=("Faith, Way of the Turtle - the entry and exit channel structure",),
        ),
        examples=(
            StrategyExample(
                title="Turtle 20/10",
                description="The published Turtle System 1 channel pair on daily bars.",
                instrument="NIFTY",
                timeframe=Timeframe.D1,
                params={"entry_period": 20, "exit_period": 10, "stop_atr_multiple": 2.0},
            ),
            StrategyExample(
                title="Slow 55/20, long only",
                description="The longer Turtle channel, long-only for a cash equity account.",
                instrument="RELIANCE",
                timeframe=Timeframe.D1,
                params={"entry_period": 55, "exit_period": 20, "direction": "long_only"},
            ),
        ),
        changelog=(
            ChangelogEntry(
                version="1.0.0",
                date="2026-07-30",
                changes=(
                    "First release on the Strategy Framework.",
                    "Separate entry and exit channel periods; current bar excluded from both.",
                ),
            ),
        ),
    )

    parameters = (
        period_param(
            "entry_period",
            description="Lookback for the breakout channel.",
            default=20,
            minimum=2,
            maximum=300,
            order=10,
        ),
        period_param(
            "exit_period",
            description="Lookback for the opposite channel that closes the trade.",
            default=10,
            minimum=2,
            maximum=300,
            order=20,
            tooltip="Shorter than the entry period keeps winners running longer than losers.",
        ),
        ParamSpec(
            name="require_close_beyond",
            type=ParamType.BOOLEAN,
            description=(
                "Require the close beyond the channel. Off triggers on the bar's "
                "high or low touching it instead."
            ),
            default=True,
            group=GROUP_SIGNAL,
            display_order=30,
            tooltip=(
                "Closes are the conservative choice: an intrabar poke through the "
                "channel that closes back inside is not a breakout."
            ),
        ),
        direction_param(),
        capital_pct_param(),
        *atr_stop_params(stop_default=2.0, target_default=0.0),
        max_bars_param(),
        fractional_param(),
    )

    def declare_indicators(self) -> Mapping[str, Indicator]:
        return {
            "entry_channel": DonchianChannel(
                self.params.integer("entry_period"), exclude_current=True
            ),
            "exit_channel": DonchianChannel(
                self.params.integer("exit_period"), exclude_current=True
            ),
        }

    def declare_risk(self) -> RiskRules:
        return atr_risk(self.params)

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        upper = view.value("entry_channel", "upper")
        lower = view.value("entry_channel", "lower")
        high_price, low_price = self._reference_prices(view)

        broke_up = self.check(
            "Broke Above Entry Channel",
            passed=upper is not None and high_price > upper,
            actual="warming up" if upper is None else f"{high_price:.4f} vs high {upper:.4f}",
            expected="above the prior channel high",
        )
        broke_down = self.check(
            "Broke Below Entry Channel",
            passed=lower is not None and low_price < lower,
            actual="warming up" if lower is None else f"{low_price:.4f} vs low {lower:.4f}",
            expected="below the prior channel low",
        )

        if broke_up:
            return EntrySignal(PositionSide.LONG, "Close broke above the prior channel high")
        if broke_down:
            return EntrySignal(PositionSide.SHORT, "Close broke below the prior channel low")
        return None

    def exit_signal(self, view: MarketView) -> ExitSignal | None:
        position = view.position
        if position is None:
            return None
        is_long = getattr(position, "side", "") == PositionSide.LONG.value
        upper = view.value("exit_channel", "upper")
        lower = view.value("exit_channel", "lower")
        high_price, low_price = self._reference_prices(view)

        long_exit = self.check(
            "Long Broke Below Exit Channel",
            passed=is_long and lower is not None and low_price < lower,
            actual="warming up" if lower is None else f"{low_price:.4f} vs low {lower:.4f}",
            expected="below the exit channel low while long",
        )
        short_exit = self.check(
            "Short Broke Above Exit Channel",
            passed=not is_long and upper is not None and high_price > upper,
            actual="warming up" if upper is None else f"{high_price:.4f} vs high {upper:.4f}",
            expected="above the exit channel high while short",
        )
        if long_exit or short_exit:
            return ExitSignal("Opposite Donchian channel broke against the position")
        return None

    def _reference_prices(self, view: MarketView) -> tuple[float, float]:
        """Prices compared against the channel: close, or the bar extremes."""
        if self.params.flag("require_close_beyond"):
            return view.bar.close, view.bar.close
        return view.bar.high, view.bar.low
