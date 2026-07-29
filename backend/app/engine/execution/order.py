"""Submitted orders."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import OrderStatus, OrderType


@dataclass
class Order:
    """One market order submitted by a strategy."""

    id: int
    order_type: OrderType
    quantity: float
    submitted_bar_index: int
    submitted_ts: int
    status: OrderStatus = OrderStatus.PENDING
    fill_price: float | None = None
    fill_ts: int | None = None
    filled_bar_index: int | None = None
    commission: float = 0.0
    slippage_cost: float = 0.0
    rejection_reason: str | None = None
