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
    exit_reason: str | None = None
    initial_stop_level: float | None = None
    trailing_stop_at_exit: float | None = None
    highest_price_reached: float | None = None
    lowest_price_reached: float | None = None
    max_favorable_excursion: float | None = None
    max_adverse_excursion: float | None = None
    max_profit: float | None = None
    max_drawdown_in_trade: float | None = None
