"""Cash and position tracking."""

from __future__ import annotations

from app.domain.enums import PositionSide
from app.domain.money import round_money
from app.engine.execution.position import Position, PositionView


class PortfolioManager:
    """Tracks cash and the single open position."""

    def __init__(self, initial_capital: float) -> None:
        self.initial_capital = initial_capital
        self.cash = round_money(initial_capital)
        self.position: Position | None = None

    @property
    def has_position(self) -> bool:
        return self.position is not None

    def position_view(self) -> PositionView | None:
        if self.position is None:
            return None
        return PositionView.from_position(self.position)

    def open_long(
        self,
        *,
        quantity: float,
        fill_price: float,
        fill_ts: int,
        entry_bar_index: int,
        commission: float,
        slippage_cost: float,
    ) -> None:
        cost = round_money(quantity * fill_price + commission)
        self.cash = round_money(self.cash - cost)
        self.position = Position(
            side=PositionSide.LONG,
            quantity=quantity,
            entry_price=fill_price,
            entry_ts=fill_ts,
            entry_bar_index=entry_bar_index,
            entry_commission=commission,
            entry_slippage_cost=slippage_cost,
        )

    def open_short(
        self,
        *,
        quantity: float,
        fill_price: float,
        fill_ts: int,
        entry_bar_index: int,
        commission: float,
        slippage_cost: float,
    ) -> None:
        proceeds = round_money(quantity * fill_price - commission)
        self.cash = round_money(self.cash + proceeds)
        self.position = Position(
            side=PositionSide.SHORT,
            quantity=quantity,
            entry_price=fill_price,
            entry_ts=fill_ts,
            entry_bar_index=entry_bar_index,
            entry_commission=commission,
            entry_slippage_cost=slippage_cost,
        )

    def close_position(self) -> Position:
        if self.position is None:
            raise RuntimeError("No open position to close")
        closed = self.position
        self.position = None
        return closed

    def credit_cash(self, amount: float) -> None:
        self.cash = round_money(self.cash + amount)

    def debit_cash(self, amount: float) -> None:
        self.cash = round_money(self.cash - amount)
