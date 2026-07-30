"""``StrategyBase`` - the contract every library strategy implements.

## What a strategy is allowed to contain

Exactly five things, per Part 1 of the framework brief:

* **Indicators** - declared in :meth:`StrategyBase.declare_indicators`.
* **Conditions** - evaluated through :meth:`StrategyBase.check`, which traces
  them for the Decision Inspector on the way through.
* **Entry rules** - :meth:`StrategyBase.entry_signal`.
* **Exit rules** - :meth:`StrategyBase.exit_signal`.
* **Risk rules** - declared in :meth:`StrategyBase.declare_risk`.

## What it is structurally unable to contain

``on_bar`` is implemented here and is not meant to be overridden. It is the only
code that talks to the execution context, so a strategy has no place to put
order submission, cash arithmetic, commission, slippage or fill logic even if
its author wanted to. Sizing is *declared* as a risk rule and computed in
``risk.py``. That is the whole point: the engine's execution mathematics stay in
the engine, and adding a strategy touches no engine file.

## Lifecycle

``on_start`` builds the declared indicators once. Each ``on_bar`` then:

1. feeds every indicator the new bar and publishes their values for the Bar
   Inspector;
2. reconciles the framework's per-trade risk state against the real position;
3. returns early while warming up, tracing why;
4. if a position is open: checks risk exits, then the strategy's exit rules;
5. if flat: checks session entry windows, then the strategy's entry rules, then
   resolves a size and submits.

Orders still fill at the next bar's open - nothing here changes that.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Final

from app.domain.enums import PositionSide
from app.engine.bars import Bar
from app.engine.context import ExecutionContext
from app.engine.indicators.base import PRIMARY_OUTPUT, Indicator
from app.engine.indicators.session import SessionClock
from app.engine.indicators.volatility import AverageTrueRange
from app.engine.strategy.metadata import StrategyMetadata
from app.engine.strategy.params import ParamSpec, ParamValue, ParamValues, resolve_or_raise
from app.engine.strategy.risk import (
    MIN_QUANTITY,
    RiskRules,
    TradeRiskState,
    evaluate_risk_exit,
)

#: Optional parameter name a strategy may declare to pick its exchange timezone.
SESSION_TIMEZONE_PARAM: Final = "session_timezone"
#: Optional parameter name a strategy may declare to restrict trade direction.
DIRECTION_PARAM: Final = "direction"

DIRECTION_LONG_ONLY: Final = "long_only"
DIRECTION_SHORT_ONLY: Final = "short_only"
DIRECTION_BOTH: Final = "both"

#: Indicator values are traced for display only; four decimals keeps the Bar
#: Inspector readable without pretending to more precision than a float has.
_TRACE_DECIMALS: Final = 4


@dataclass(frozen=True, slots=True)
class EntrySignal:
    """A decision to open a position. Quantity is decided by the risk rules."""

    side: PositionSide
    reason: str


@dataclass(frozen=True, slots=True)
class ExitSignal:
    """A decision to close the open position for a strategy-logic reason."""

    reason: str


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    """Exchange-local view of the current bar, for strategies that need one."""

    local_time: str
    session_date: str
    minutes_into_day: int
    bars_in_session: int


class MarketView:
    """Everything a rule may read about the current bar.

    Deliberately read-only and deliberately narrow: no bar history, no future
    bars, no portfolio internals. Indicator values are resolved by name, with
    the previous bar's values available so crossover rules do not have to keep
    their own state.
    """

    __slots__ = ("_current", "_previous", "bar", "bar_index", "bars_held", "position", "session")

    def __init__(
        self,
        *,
        bar: Bar,
        bar_index: int,
        current: Mapping[str, float | None],
        previous: Mapping[str, float | None],
        position: object | None,
        bars_held: int,
        session: SessionSnapshot | None,
    ) -> None:
        self.bar = bar
        self.bar_index = bar_index
        self.bars_held = bars_held
        self.position = position
        self.session = session
        self._current = current
        self._previous = previous

    def _key(self, name: str, output: str | None) -> str:
        return name if output is None else f"{name}.{output}"

    def value(self, name: str, output: str | None = None) -> float | None:
        """Current value of an indicator output, or None while it warms up."""
        return self._current.get(self._key(name, output))

    def previous(self, name: str, output: str | None = None) -> float | None:
        """The same output one bar ago."""
        return self._previous.get(self._key(name, output))

    def require(self, name: str, output: str | None = None) -> float:
        """Read a value that must exist. Only valid after warmup has completed."""
        value = self.value(name, output)
        if value is None:
            raise ValueError(
                f"Indicator '{self._key(name, output)}' has no value on bar {self.bar_index}; "
                "declare enough warmup bars before reading it"
            )
        return value

    def has(self, *names: str) -> bool:
        """True when every named output currently has a value."""
        return all(self._current.get(name) is not None for name in names)

    def crossed_above(self, name: str, other: str) -> bool:
        """``name`` was at or below ``other`` last bar and is above it now."""
        return self._crossed(name, other, upward=True)

    def crossed_below(self, name: str, other: str) -> bool:
        return self._crossed(name, other, upward=False)

    def _crossed(self, name: str, other: str, *, upward: bool) -> bool:
        now_a, now_b = self.value(name), self.value(other)
        was_a, was_b = self.previous(name), self.previous(other)
        if None in (now_a, now_b, was_a, was_b):
            return False
        assert now_a is not None and now_b is not None
        assert was_a is not None and was_b is not None
        if upward:
            return was_a <= was_b and now_a > now_b
        return was_a >= was_b and now_a < now_b

    def crossed_level_above(self, name: str, level: float) -> bool:
        was, now = self.previous(name), self.value(name)
        return was is not None and now is not None and was <= level < now

    def crossed_level_below(self, name: str, level: float) -> bool:
        was, now = self.previous(name), self.value(name)
        return was is not None and now is not None and was >= level > now

    def rising(self, name: str, output: str | None = None) -> bool:
        was, now = self.previous(name, output), self.value(name, output)
        return was is not None and now is not None and now > was

    def falling(self, name: str, output: str | None = None) -> bool:
        was, now = self.previous(name, output), self.value(name, output)
        return was is not None and now is not None and now < was


class StrategyBase:
    """Base class for every strategy in the library.

    Subclasses set ``metadata`` and ``parameters`` as class attributes and
    override the rule hooks. They never override ``on_bar``.
    """

    #: Declared once per class. ``validation.py`` rejects a class without one.
    metadata: ClassVar[StrategyMetadata]
    #: Typed parameter declarations; drives the UI, validation and optimisation.
    parameters: ClassVar[tuple[ParamSpec, ...]] = ()

    #: Set by the engine before ``on_start``.
    ctx: ExecutionContext

    def __init__(self, params: Mapping[str, object] | None = None) -> None:
        self.params: ParamValues = resolve_or_raise(self.parameters, params)
        self._indicators: dict[str, Indicator] = {}
        self._risk: RiskRules = RiskRules()
        self._atr: AverageTrueRange | None = None
        self._clock: SessionClock | None = None
        self._current: dict[str, float | None] = {}
        self._previous: dict[str, float | None] = {}
        self._trade: TradeRiskState | None = None
        self._warmup_bars = 0
        self._bars_seen = 0

    # ------------------------------------------------------------------
    # Author hooks
    # ------------------------------------------------------------------

    def declare_indicators(self) -> Mapping[str, Indicator]:
        """Indicators this strategy reads, keyed by the name rules refer to."""
        return {}

    def declare_risk(self) -> RiskRules:
        """Sizing and protective exits. Defaults to one unit and no stops."""
        return RiskRules()

    def entry_signal(self, view: MarketView) -> EntrySignal | None:
        """Entry rules. Return a signal to open, or None to stay flat."""
        return None

    def exit_signal(self, view: MarketView) -> ExitSignal | None:
        """Exit rules beyond the declared risk rules. Return None to hold."""
        return None

    def extra_warmup_bars(self) -> int:
        """Warmup a strategy needs beyond the longest indicator it declares."""
        return 0

    # ------------------------------------------------------------------
    # Author helpers
    # ------------------------------------------------------------------

    def check(
        self,
        name: str,
        *,
        passed: bool,
        actual: object = "",
        expected: object = "",
    ) -> bool:
        """Evaluate and trace one condition, returning whether it passed.

        Traces both outcomes, which is what makes the Decision Inspector able
        to answer "why did nothing happen on this bar". Evaluate every check
        into a local before combining them - ``a and b`` short-circuits and
        would leave ``b`` untraced.
        """
        self.ctx.trace_condition(
            name,
            actual=_render(actual),
            expected=_render(expected),
            passed=passed,
        )
        return passed

    def note(self, *parts: object) -> None:
        """Write a line into the run log."""
        self.ctx.log(*parts)

    def operand(self, name: str, value: float | None, *, label: str = "", unit: str = "") -> None:
        """Publish one raw number behind a decision, for the decision log.

        ``None`` is skipped rather than stored as zero: "no stop distance" and "a
        stop distance of zero" are different facts, and a reader that cannot tell
        them apart cannot explain a sizing rule that declined to size.
        """
        if value is None:
            return
        self.ctx.trace_operand(name, float(value), label=label or name, unit=unit)

    @property
    def risk(self) -> RiskRules:
        return self._risk

    @property
    def warmup_bars(self) -> int:
        return self._warmup_bars

    @property
    def session_timezone(self) -> str:
        """Exchange timezone, from the ``session_timezone`` parameter if declared."""
        if SESSION_TIMEZONE_PARAM in self.params:
            return self.params.text(SESSION_TIMEZONE_PARAM)
        return "UTC"

    def direction_allows(self, side: PositionSide) -> bool:
        """Is this side permitted by the metadata and the ``direction`` parameter?"""
        if side is PositionSide.LONG and not self.metadata.supports_long:
            return False
        if side is PositionSide.SHORT and not self.metadata.supports_short:
            return False
        if DIRECTION_PARAM not in self.params:
            return True
        choice = self.params.text(DIRECTION_PARAM)
        if choice == DIRECTION_LONG_ONLY:
            return side is PositionSide.LONG
        if choice == DIRECTION_SHORT_ONLY:
            return side is PositionSide.SHORT
        return True

    # ------------------------------------------------------------------
    # Engine hooks - not part of the authoring surface
    # ------------------------------------------------------------------

    def on_start(self) -> None:
        self._indicators = dict(self.declare_indicators())
        self._risk = self.declare_risk()
        if self._risk.needs_atr:
            self._atr = AverageTrueRange(self._risk.atr_period)
        if self._risk.needs_session_clock:
            self._clock = SessionClock(self.session_timezone)

        indicator_warmup = max(
            (indicator.warmup_bars for indicator in self._indicators.values()), default=0
        )
        atr_warmup = self._atr.warmup_bars if self._atr is not None else 0
        self._warmup_bars = max(indicator_warmup, atr_warmup) + self.extra_warmup_bars()

    def on_bar(self, bar: Bar) -> None:
        self._bars_seen += 1
        bar_index = self.ctx.current_bar_index

        if self._clock is not None:
            self._clock.advance(bar)
        if self._atr is not None:
            self._atr.update(bar)
        for indicator in self._indicators.values():
            indicator.update(bar)

        self._previous = self._current
        self._current = self._collect_values()
        self._trace_values()

        position = self.ctx.position
        self._sync_trade(position, bar=bar, bar_index=bar_index)
        self._trace_portfolio(position)

        view = MarketView(
            bar=bar,
            bar_index=bar_index,
            current=self._current,
            previous=self._previous,
            position=position,
            bars_held=0 if self._trade is None else bar_index - self._trade.entry_bar_index,
            session=self._session_snapshot(),
        )

        if not self.check(
            "Warmup Complete",
            passed=self._bars_seen > self._warmup_bars,
            actual=f"{self._bars_seen} bars seen",
            expected=f"more than {self._warmup_bars}",
        ):
            return

        if position is not None:
            self._handle_open_position(view)
            return
        self._handle_flat(view)

    def on_stop(self) -> None:
        """No-op by default. A strategy may override for end-of-run logging."""

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _handle_open_position(self, view: MarketView) -> None:
        trade = self._trade
        if trade is not None:
            atr_now = None if self._atr is None else self._atr.value
            # The protective levels a risk exit is compared against. Without them
            # a stop-loss exit shows only that it fired, not what it fired on.
            self.operand("risk_stop_level", trade.stop_level, label="Stop level")
            self.operand("risk_target_level", trade.target_level, label="Target level")
            self.operand(
                "risk_trailing_level",
                trade.trailing_level(self._risk, atr_now),
                label="Trailing stop level",
            )
            self.operand("risk_best_price", trade.best_price, label="Best price reached")
            self.operand("risk_entry_price", trade.entry_price, label="Entry price")
            self.operand("risk_bars_held", float(view.bars_held), label="Bars held", unit="bars")
            self.operand("risk_atr", atr_now, label="ATR")
            risk_exit = evaluate_risk_exit(
                trade,
                bar=view.bar,
                bars_held=view.bars_held,
                rules=self._risk,
                atr=atr_now,
                clock=self._clock,
            )
            self.check(
                "Risk Exit Triggered",
                passed=risk_exit is not None,
                actual="none" if risk_exit is None else risk_exit.code,
                expected="any protective rule",
            )
            if risk_exit is not None:
                self.note(f"Risk exit ({risk_exit.code}): {risk_exit.description}")
                self.ctx.close()
                return

        signal = self.exit_signal(view)
        self.check(
            "Exit Rules Met",
            passed=signal is not None,
            actual="no exit signal" if signal is None else signal.reason,
            expected="an exit signal",
        )
        if signal is not None:
            self.note(f"Exit: {signal.reason}")
            self.ctx.close()

    def _handle_flat(self, view: MarketView) -> None:
        if self._risk.no_entry_after is not None and self._clock is not None:
            blocked = self._clock.is_at_or_after(self._risk.no_entry_after)
            if not self.check(
                "Inside Entry Window",
                passed=not blocked,
                actual=f"{self._clock.local_time:%H:%M} exchange time",
                expected=f"before {self._risk.no_entry_after}",
            ):
                return

        signal = self.entry_signal(view)
        self.check(
            "Entry Rules Met",
            passed=signal is not None,
            actual="no entry signal" if signal is None else signal.reason,
            expected="an entry signal",
        )
        if signal is None:
            return

        if not self.check(
            "Direction Permitted",
            passed=self.direction_allows(signal.side),
            actual=signal.side.value,
            expected=self.metadata.direction_label.lower(),
        ):
            return

        capital = self.ctx.cash
        price = view.bar.close
        sizing = self._risk.resolve_quantity_detail(
            capital=capital,
            price=price,
            atr=None if self._atr is None else self._atr.value,
        )
        quantity = sizing.quantity
        # Every input to the size, so a zero is attributable rather than just
        # observed. The floored-to-zero case in particular is invisible from the
        # final quantity alone - it looks identical to "the rule sized nothing".
        self.operand("size_capital", capital, label="Capital available")
        self.operand("size_price", price, label="Price used for sizing")
        self.operand("size_raw_quantity", sizing.raw, label="Size before rounding", unit="units")
        self.operand("size_quantity", quantity, label="Size submitted", unit="units")
        self.operand("size_stop_distance", sizing.stop_distance, label="Stop distance")
        if not self.check(
            "Position Size Available",
            passed=quantity > MIN_QUANTITY,
            actual=(
                f"{_render(sizing.raw)} floored to 0 (whole units only)"
                if sizing.floored_to_zero
                else _render(quantity)
            ),
            expected="greater than zero",
        ):
            return

        self.note(f"Entry ({signal.side.value}) x{_render(quantity)}: {signal.reason}")
        if signal.side is PositionSide.LONG:
            self.ctx.buy(quantity)
        else:
            self.ctx.sell(quantity)

    def _collect_values(self) -> dict[str, float | None]:
        """Flatten indicators into ``name`` and ``name.output`` lookups."""
        values: dict[str, float | None] = {}
        for name, indicator in self._indicators.items():
            snapshot = indicator.snapshot()
            values[name] = snapshot[indicator.outputs[0]]
            if indicator.outputs != (PRIMARY_OUTPUT,):
                for output, value in snapshot.items():
                    values[f"{name}.{output}"] = value
        return values

    def _trace_values(self) -> None:
        for key, value in self._current.items():
            if value is not None:
                self.ctx.trace_indicator(key, round(value, _TRACE_DECIMALS))

    def _trace_portfolio(self, position: object | None) -> None:
        """Portfolio state on every bar, warmup included.

        Recorded before the warmup gate returns, because "the account had this
        much cash on this bar" is a fact whether or not any rule ran.
        """
        self.operand("cash", self.ctx.cash, label="Cash")
        if position is None:
            return
        self.operand(
            "position_quantity",
            float(getattr(position, "quantity", 0.0)),
            label="Position size",
            unit="units",
        )

    def _sync_trade(self, position: object | None, *, bar: Bar, bar_index: int) -> None:
        """Keep framework risk state aligned with the engine's real position."""
        if position is None:
            self._trade = None
            return

        side = PositionSide(getattr(position, "side"))  # noqa: B009 - PositionView is a dataclass
        entry_price = float(getattr(position, "entry_price"))  # noqa: B009
        if self._trade is None or self._trade.side is not side:
            self._trade = TradeRiskState.open(
                side=side,
                entry_price=entry_price,
                entry_bar_index=bar_index,
                atr=None if self._atr is None else self._atr.value,
                rules=self._risk,
            )
        self._trade.observe(bar)

    def _session_snapshot(self) -> SessionSnapshot | None:
        clock = self._clock or self._borrowed_clock()
        if clock is None:
            return None
        return SessionSnapshot(
            local_time=f"{clock.local_time:%H:%M}",
            session_date=clock.session_date,
            minutes_into_day=clock.minutes_into_day,
            bars_in_session=clock.bars_in_session,
        )

    def _borrowed_clock(self) -> SessionClock | None:
        """Reuse a session clock an indicator already maintains.

        ``OpeningRange`` and ``SessionVwap`` each keep one. Borrowing avoids a
        third timezone conversion per bar and guarantees the strategy and its
        indicators agree on where a session boundary is.
        """
        for indicator in self._indicators.values():
            clock = getattr(indicator, "clock", None)
            if isinstance(clock, SessionClock):
                return clock
        return None


def _render(value: object) -> str:
    """Format a traced value the way the inspectors display it."""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".") if value % 1 else str(int(value))
    return str(value)


def default_parameter_values(strategy_class: type[StrategyBase]) -> dict[str, ParamValue]:
    """Defaults for a strategy class, for callers that only have the type."""
    return {spec.name: spec.default for spec in strategy_class.parameters}
