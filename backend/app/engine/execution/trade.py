"""Completed round-trip trades."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import PositionSide


@dataclass(frozen=True)
class Trade:
    """One closed position from entry to exit."""

    seq: int
    side: PositionSide
    quantity: float
    entry_ts: int
    entry_price: float
    exit_ts: int
    exit_price: float
    gross_pnl: float
    commission: float
    slippage_cost: float
    net_pnl: float
    bars_held: int
