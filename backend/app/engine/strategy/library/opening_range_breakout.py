"""Opening Range Breakout - break the first N minutes of the session."""

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
from app.engine.indicators.session import OpeningRange
from app.engine.strategy.framework import EntrySignal, ExitSignal, MarketView, StrategyBase
from app.engine.strategy.library._shared import (
    GROUP_FILTERS,
    GROUP_SIGNAL,
    capital_pct_param,
    direction_param,
    fractional_param,
    max_bars_param,
    percent_risk,
    percent_stop_params,
    session_timezone_param,
    time_param,
    trailing_stop_params,
)
from app.engine.strategy.metadata import (
    ChangelogEntry,
    StrategyDocumentation,
    StrategyExample,
    StrategyMetadata,
)
from app.engine.strategy.params import ParamSpec
from app.engine.strategy.risk import RiskRules


class OpeningRangeBreakoutStrategy(StrategyBase):
    """Buy a break above the opening range high, sell a break below its low."""

    metadata = StrategyMetadata(
        id="opening_range_breakout",
        name="Opening Range Breakout",
        description=(
            "Marks the high and low of the first N minutes of each session and trades "
            "the first break of that range, flat by the session close."
        ),
        version="1.0.0",
        author="Platform",
        category=StrategyCategory.BREAKOUT,
        markets=(MarketType.EQUITY, MarketType.INDEX, MarketType.FUTURES, MarketType.OPTIONS),
        timeframes=(Timeframe.M1, Timeframe.M3, Timeframe.M5, Timeframe.M15),
        tags=("breakout", "intraday", "opening-range", "session"),
        risk_level=RiskLevel.HIGH,
        supports_long=True,
        supports_short=True,
        supports_intraday=True,
        supports_swing=False,
        supports_position_trading=False,
        documentation=StrategyDocumentation(
            overview=(
                "The opening auction and the first few minutes after it establish the "
                "session's initial balance. This strategy treats a break of that range "
                "as the session choosing a direction. Two details do most of the work: "
                "the range is only usable once its window has *closed*, and only one "
                "trade per session is taken, so a choppy day cannot fire the same "
                "signal a dozen times."
            ),
            indicators=(
                "Opening range high and low over the first `range_minutes` of the session",
                "Range width, used by the optional maximum-width filter",
            ),
            entry_rules=(
                "Long when the close breaks above the completed opening range high",
                "Short when the close breaks below the completed opening range low",
                "At most `max_trades_per_session` entries per session",
                "No entries at or after `no_entry_after` exchange time",
                "With `max_range_pct` set, the range must be narrower than that "
                "percentage of price - a very wide opening range means the move has "
                "already happened",
            ),
            exit_rules=(
                "Close when price falls back inside the opposite side of the range",
                "Flatten unconditionally at `exit_at_time` exchange time",
                "Percent stop and target can exit sooner",
            ),
            risk_rules=(
                "Hard session exit; nothing is carried overnight",
                "One trade per session by default",
            ),
            known_limitations=(
                "Requires intraday bars whose granularity divides the range window. A "
                "15-minute bar with a 15-minute range gives a single-bar range.",
                "The first session in a dataset is usually unusable because the data "
                "may start after the opening range window.",
                "Fills happen at the next bar's open, which on a breakout is the worst "
                "case: the gap between signal and fill is where this strategy's real "
                "slippage lives.",
                "No holiday or half-day calendar: a session is whatever bars share a local date.",
            ),
        ),
        examples=(
            StrategyExample(
                title="NSE 15-minute opening range",
                description=(
                    "The standard Indian-market ORB: 09:15-09:30 range, 5-minute bars, "
                    "flat by 15:15."
                ),
                instrument="BANKNIFTY",
                timeframe=Timeframe.M5,
                params={
                    "session_timezone": "Asia/Kolkata",
                    "session_start": "09:15",
                    "range_minutes": 15,
                    "no_entry_after": "14:30",
                    "exit_at_time": "15:15",
                },
            ),
            StrategyExample(
                title="US 30-minute opening range, long only",
                description="09:30-10:00 Eastern range on 5-minute bars, flat by 15:50.",
                instrument="SPY",
                timeframe=Timeframe.M5,
                params={
                    "session_timezone": "America/New_York",
                    "session_start": "09:30",
                    "range_minutes": 30,
                    "no_entry_after": "15:00",
                    "exit_at_time": "15:50",
                    "direction": "long_only",
                },
            ),
        ),
        changelog=(
            ChangelogEntry(
                version="1.0.0",
                date="2026-07-30",
                changes=(
                    "First release on the Strategy Framework.",
                    "Range is only tradable once its window has closed.",
                    "Per-session trade cap and optional maximum range width filter.",
                ),
            ),
        ),
    )

    parameters = (
        ParamSpec(
            name="range_minutes",
            type=ParamType.INTEGER,
            description="Length of the opening range window, in minutes from the session start.",
            default=15,
            minimum=1,
            maximum=240,
            step=1,
            group=GROUP_SIGNAL,
            display_order=10,
            tooltip="Should be a whole number of bars at your chosen timeframe.",
        ),
        ParamSpec(
            name="max_trades_per_session",
            type=ParamType.INTEGER,
            description="How many entries are allowed per session.",
            default=1,
            minimum=1,
            maximum=10,
            step=1,
            group=GROUP_SIGNAL,
            display_order=20,
            tooltip="One is the classic rule and avoids re-entering a chopping range.",
        ),
        ParamSpec(
            name="max_range_pct",
            type=ParamType.PERCENTAGE,
            description=(
                "Skip the session if the opening range is wider than this percent of "
                "price. 0 disables the filter."
            ),
            default=0.0,
            minimum=0.0,
            maximum=20.0,
            step=0.1,
            group=GROUP_FILTERS,
            display_order=10,
        ),
        session_timezone_param(default="Asia/Kolkata"),
        time_param(
            "session_start",
            description="Exchange-local time the session (and the opening range) begins.",
            default="09:15",
            order=15,
        ),
        time_param(
            "no_entry_after",
            description="Exchange-local time after which no new position is opened.",
            default="14:30",
            order=20,
        ),
        time_param(
            "exit_at_time",
            description="Exchange-local time at which any open position is flattened.",
            default="15:15",
            order=30,
        ),
        direction_param(),
        capital_pct_param(),
        *percent_stop_params(stop_default=1.0, target_default=2.0),
        max_bars_param(),
        fractional_param(),
        *trailing_stop_params(),
    )

    def __init__(self, params: Mapping[str, object] | None = None) -> None:
        super().__init__(params)
        # Per-session entry accounting. Keyed on the local session date so it
        # resets without needing a session-boundary callback.
        self._session_date: str | None = None
        self._entries_this_session = 0

    def declare_indicators(self) -> Mapping[str, Indicator]:
        return {
            "opening_range": OpeningRange(
                timezone=self.session_timezone,
                session_start=self.params.text("session_start"),
                range_minutes=self.params.integer("range_minutes"),
            )
        }

    def declare_risk(self) -> RiskRules:
        return percent_risk(
            self.params,
            exit_at_time=self.params.text("exit_at_time"),
            no_entry_after=self.params.text("no_entry_after"),
        )

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        self._roll_session(view)

        high = view.value("opening_range", "high")
        low = view.value("opening_range", "low")
        close = view.bar.close

        range_ready = self.check(
            "Opening Range Complete",
            passed=high is not None and low is not None,
            actual="not yet formed" if high is None else f"{low:.4f} to {high:.4f}",
            expected="the range window has closed",
        )
        under_cap = self.check(
            "Session Trade Cap Not Reached",
            passed=self._entries_this_session < self.params.integer("max_trades_per_session"),
            actual=f"{self._entries_this_session} taken",
            expected=f"fewer than {self.params.integer('max_trades_per_session')}",
        )
        width_ok = self._width_gate(view)

        broke_up = self.check(
            "Broke Above Opening Range High",
            passed=high is not None and close > high,
            actual="range not formed" if high is None else f"{close:.4f} vs high {high:.4f}",
            expected="close above the opening range high",
        )
        broke_down = self.check(
            "Broke Below Opening Range Low",
            passed=low is not None and close < low,
            actual="range not formed" if low is None else f"{close:.4f} vs low {low:.4f}",
            expected="close below the opening range low",
        )

        if not (range_ready and under_cap and width_ok):
            return None
        if broke_up:
            self._entries_this_session += 1
            return EntrySignal(PositionSide.LONG, "Close broke above the opening range high")
        if broke_down:
            self._entries_this_session += 1
            return EntrySignal(PositionSide.SHORT, "Close broke below the opening range low")
        return None

    def exit_signal(self, view: MarketView) -> ExitSignal | None:
        position = view.position
        high = view.value("opening_range", "high")
        low = view.value("opening_range", "low")
        if position is None or high is None or low is None:
            return None
        is_long = getattr(position, "side", "") == PositionSide.LONG.value
        close = view.bar.close

        failed = self.check(
            "Price Fell Back Inside Range",
            passed=(close < low) if is_long else (close > high),
            actual=f"{close:.4f} vs range {low:.4f} to {high:.4f}",
            expected="close back through the far side of the opening range",
        )
        return ExitSignal("Breakout failed back through the opening range") if failed else None

    def _roll_session(self, view: MarketView) -> None:
        session = view.session
        if session is None:
            return
        if session.session_date != self._session_date:
            self._session_date = session.session_date
            self._entries_this_session = 0

    def _width_gate(self, view: MarketView) -> bool:
        threshold = self.params.number("max_range_pct")
        if threshold <= 0:
            return True
        width = view.value("opening_range", "width")
        close = view.bar.close
        as_percent = None if width is None or close == 0 else width / close * 100.0
        return self.check(
            "Opening Range Narrow Enough",
            passed=as_percent is not None and as_percent <= threshold,
            actual="range not formed" if as_percent is None else f"{as_percent:.3f}% of price",
            expected=f"at or below {threshold:g}%",
        )
