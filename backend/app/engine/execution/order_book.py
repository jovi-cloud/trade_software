"""Pending order queue between bars."""

from __future__ import annotations

from app.domain.enums import OrderStatus, OrderType
from app.engine.execution.order import Order


class OrderBook:
    """Holds orders until the next bar open fill pass."""

    def __init__(self) -> None:
        self._pending: list[Order] = []
        self._history: list[Order] = []
        self._next_id = 1

    @property
    def history(self) -> tuple[Order, ...]:
        return tuple(self._history)

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def submit(
        self,
        *,
        order_type: OrderType,
        quantity: float,
        submitted_bar_index: int,
        submitted_ts: int,
    ) -> Order:
        order = Order(
            id=self._next_id,
            order_type=order_type,
            quantity=quantity,
            submitted_bar_index=submitted_bar_index,
            submitted_ts=submitted_ts,
        )
        self._next_id += 1
        self._pending.append(order)
        self._history.append(order)
        return order

    def take_pending(self) -> list[Order]:
        pending = self._pending
        self._pending = []
        return pending

    def mark_rejected(self, order: Order, reason: str) -> None:
        order.status = OrderStatus.REJECTED
        order.rejection_reason = reason
