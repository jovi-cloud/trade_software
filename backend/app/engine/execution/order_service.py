"""Strategy-facing order submission with single-position guardrails."""

from __future__ import annotations

from app.domain.enums import OrderType
from app.engine.bars import Bar
from app.engine.execution.order import Order
from app.engine.execution.order_book import OrderBook
from app.engine.execution.portfolio import PortfolioManager
from app.engine.explain.collector import ExplainCollector


class OrderService:
    """Accepts buy/sell/close requests from the execution context."""

    def __init__(
        self,
        order_book: OrderBook,
        portfolio: PortfolioManager,
        warnings: list[str],
        *,
        collector: ExplainCollector | None = None,
    ) -> None:
        self._order_book = order_book
        self._portfolio = portfolio
        self._warnings = warnings
        self._collector = collector
        self._current_bar_index = -1
        self._current_ts = 0

    def set_bar_context(self, *, bar_index: int, bar: Bar) -> None:
        self._current_bar_index = bar_index
        self._current_ts = bar.ts

    def buy(self, quantity: float = 1.0) -> Order | None:
        if quantity <= 0:
            self._warnings.append("buy() ignored: quantity must be positive")
            self._record_signal(
                action="Buy",
                quantity=quantity,
                accepted=False,
                rejection_reason="quantity must be positive",
            )
            return None
        if self._portfolio.has_position:
            self._warnings.append(
                "buy() ignored: a position is already open; close it before opening another"
            )
            self._record_signal(
                action="Buy",
                quantity=quantity,
                accepted=False,
                rejection_reason="a position is already open",
            )
            return None
        order = self._order_book.submit(
            order_type=OrderType.BUY_MARKET,
            quantity=quantity,
            submitted_bar_index=self._current_bar_index,
            submitted_ts=self._current_ts,
        )
        self._record_signal(action="Buy", quantity=quantity, accepted=True)
        if self._collector is not None:
            self._collector.record_order_created(order)
            self._collector.record_order_submitted(order)
        return order

    def sell(self, quantity: float = 1.0) -> Order | None:
        if quantity <= 0:
            self._warnings.append("sell() ignored: quantity must be positive")
            self._record_signal(
                action="Sell short",
                quantity=quantity,
                accepted=False,
                rejection_reason="quantity must be positive",
            )
            return None
        if self._portfolio.has_position:
            self._warnings.append(
                "sell() ignored: a position is already open; close it before opening another"
            )
            self._record_signal(
                action="Sell short",
                quantity=quantity,
                accepted=False,
                rejection_reason="a position is already open",
            )
            return None
        order = self._order_book.submit(
            order_type=OrderType.SELL_MARKET,
            quantity=quantity,
            submitted_bar_index=self._current_bar_index,
            submitted_ts=self._current_ts,
        )
        self._record_signal(action="Sell short", quantity=quantity, accepted=True)
        if self._collector is not None:
            self._collector.record_order_created(order)
            self._collector.record_order_submitted(order)
        return order

    def close(self) -> Order | None:
        if not self._portfolio.has_position:
            self._warnings.append("close() ignored: no open position")
            self._record_signal(
                action="Close",
                quantity=0,
                accepted=False,
                rejection_reason="no open position",
            )
            return None
        position = self._portfolio.position
        assert position is not None
        order = self._order_book.submit(
            order_type=OrderType.CLOSE,
            quantity=position.quantity,
            submitted_bar_index=self._current_bar_index,
            submitted_ts=self._current_ts,
        )
        self._record_signal(action="Close", quantity=position.quantity, accepted=True)
        if self._collector is not None:
            self._collector.record_order_created(order)
            self._collector.record_order_submitted(order)
        return order

    def _record_signal(
        self,
        *,
        action: str,
        quantity: float,
        accepted: bool,
        rejection_reason: str | None = None,
    ) -> None:
        if self._collector is None:
            return
        self._collector.record_signal_generated(
            action=action,
            quantity=quantity,
            bar_index=self._current_bar_index,
            timestamp_ms=self._current_ts,
            accepted=accepted,
            rejection_reason=rejection_reason,
        )
