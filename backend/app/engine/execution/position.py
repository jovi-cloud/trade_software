"""Open position state."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import PositionSide


@dataclass
class Position:
    """A single open long or short position."""

    side: PositionSide
    quantity: float
    entry_price: float
    entry_ts: int
    entry_bar_index: int
    entry_commission: float
    entry_slippage_cost: float


@dataclass(frozen=True)
class PositionView:
    """Read-only position snapshot exposed to strategies."""

    side: str
    quantity: float
    entry_price: float

    @classmethod
    def from_position(cls, position: Position) -> PositionView:
        return cls(
            side=position.side.value,
            quantity=position.quantity,
            entry_price=position.entry_price,
        )
