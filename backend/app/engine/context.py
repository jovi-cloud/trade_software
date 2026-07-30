"""The execution context handed to a running strategy.

Exposes order methods, read-only position/cash, and logging. Orders submitted
here are queued and filled at the next bar's open (ARCHITECTURE.md 2.2).
"""

from __future__ import annotations

from app.engine.bars import Bar
from app.engine.execution.order_service import OrderService
from app.engine.execution.portfolio import PortfolioManager
from app.engine.execution.position import PositionView
from app.engine.explain.condition_collector import ConditionCollector

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
    ) -> None:
        self._initial_capital = initial_capital
        self._portfolio = portfolio
        self._order_service = order_service
        self._logs = logs
        self._condition_collector = condition_collector
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

    def buy(self, quantity: float = 1.0) -> None:
        """Submit a market buy to open a long position on the next bar open."""
        self._order_service.buy(quantity)

    def sell(self, quantity: float = 1.0) -> None:
        """Submit a market sell to open a short position on the next bar open."""
        self._order_service.sell(quantity)

    def close(self) -> None:
        """Submit a market order to close the open position on the next bar open."""
        self._order_service.close()

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
