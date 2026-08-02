"""The execution context handed to a running strategy.

Exposes order methods, read-only position/cash, and logging. Orders submitted
here are queued and filled at the next bar's open (ARCHITECTURE.md 2.2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.engine.bars import Bar
from app.engine.execution.order_service import OrderService
from app.engine.execution.portfolio import PortfolioManager
from app.engine.execution.position import PositionView
from app.engine.execution.trade_manager import TradeManager
from app.engine.explain.condition_collector import ConditionCollector
from app.engine.results.chart_data import TrailingStopCollector

if TYPE_CHECKING:
    from app.engine.strategy.risk import StopLossOverride

# A strategy logging on every bar of a multi-million-bar dataset would
# otherwise exhaust memory, so the sink is bounded and reports truncation.
MAX_LOG_ENTRIES = 1000


class LogCollector:
    """Bounded sink for strategy log output."""

    def __init__(self, limit: int = MAX_LOG_ENTRIES) -> None:
        self._entries: list[str] = []
        self._limit = limit
        self.truncated = False

    def add(self, message: str) -> None:
        if len(self._entries) >= self._limit:
            self.truncated = True
            return
        self._entries.append(message)

    @property
    def entries(self) -> tuple[str, ...]:
        return tuple(self._entries)


class ExecutionContext:
    """Strategy-facing API for one replay run."""

    def __init__(
        self,
        *,
        initial_capital: float,
        portfolio: PortfolioManager,
        order_service: OrderService,
        logs: LogCollector,
        condition_collector: ConditionCollector | None = None,
        stop_loss_override: StopLossOverride | None = None,
        trailing_stop_collector: TrailingStopCollector | None = None,
        trade_manager: TradeManager | None = None,
        exchange_timezone: str = "UTC",
        session_exit_at: str | None = None,
    ) -> None:
        self._initial_capital = initial_capital
        self._portfolio = portfolio
        self._order_service = order_service
        self._logs = logs
        self._condition_collector = condition_collector
        self.stop_loss_override = stop_loss_override
        self.trailing_stop_collector = trailing_stop_collector
        self._trade_manager = trade_manager
        self.exchange_timezone = exchange_timezone
        self.session_exit_at = session_exit_at
        self._current_bar: Bar | None = None
        self._current_bar_index = -1

    @property
    def current_bar(self) -> Bar | None:
        """The bar currently being replayed; ``None`` before the first bar."""
        return self._current_bar

    @property
    def current_bar_index(self) -> int:
        """Zero-based index of the bar currently being replayed."""
        return self._current_bar_index

    @property
    def initial_capital(self) -> float:
        return self._initial_capital

    @property
    def cash(self) -> float:
        return self._portfolio.cash

    @property
    def position(self) -> PositionView | None:
        return self._portfolio.position_view()

    @property
    def pending_trade_seq(self) -> int:
        """Sequence number the next closed trade will receive."""
        if self._trade_manager is None:
            return 1
        return self._trade_manager.trade_count + 1

    def buy(self, quantity: float = 1.0) -> None:
        """Submit a market buy to open a long position on the next bar open."""
        self._order_service.buy(quantity)

    def sell(self, quantity: float = 1.0) -> None:
        """Submit a market sell to open a short position on the next bar open."""
        self._order_service.sell(quantity)

    def close(self, *, exit_reason: str | None = None, risk_state: object | None = None) -> None:
        """Submit a market order to close the open position on the next bar open."""
        self._order_service.close(exit_reason=exit_reason, risk_state=risk_state)

    def log(self, *parts: object) -> None:
        """Record a message against this run. Appears in ``strategy_logs``."""
        self._logs.add(" ".join(str(part) for part in parts))

    def trace_condition(
        self,
        name: str,
        *,
        actual: str,
        expected: str,
        passed: bool,
    ) -> None:
        """Publish one evaluated condition for the Decision Inspector."""
        if self._condition_collector is None:
            return
        self._condition_collector.trace_condition(
            name,
            actual=actual,
            expected=expected,
            passed=passed,
        )

    def trace_indicator(self, name: str, value: float | str) -> None:
        """Publish an indicator value for the Bar Inspector market state."""
        if self._condition_collector is None:
            return
        self._condition_collector.trace_indicator(name, value)

    def trace_operand(
        self,
        name: str,
        value: float,
        *,
        label: str = "",
        unit: str = "",
    ) -> None:
        """Publish one raw number behind a verdict, for the decision log.

        Use this for the inputs to a calculation, not its conclusion: recording
        ``size_raw_quantity = 0.201`` next to a failed "Position Size Available"
        is what turns "the size was zero" into "20% of 1000 buys 0.201 shares at
        995.40, and whole-unit flooring made that zero".
        """
        if self._condition_collector is None:
            return
        self._condition_collector.trace_operand(name, value, label=label, unit=unit)

    def advance_to(self, bar: Bar, *, bar_index: int) -> None:
        """Engine-internal: point the context at the bar about to be replayed."""
        self._current_bar = bar
        self._current_bar_index = bar_index
        self._order_service.set_bar_context(bar_index=bar_index, bar=bar)

    @property
    def condition_collector(self) -> ConditionCollector | None:
        return self._condition_collector


# Phase 3A alias kept so internal imports and docs stay stable.
Context = ExecutionContext
