"""Round-trip trade recording."""

from __future__ import annotations

from app.domain.enums import PositionSide
from app.domain.money import round_money
from app.engine.execution.position import Position
from app.engine.execution.trade import Trade


class TradeManager:
    """Builds closed trades from position entry and exit fills."""

    def __init__(self) -> None:
        self._trades: list[Trade] = []
        self._next_seq = 1

    @property
    def trades(self) -> tuple[Trade, ...]:
        return tuple(self._trades)

    @property
    def trade_count(self) -> int:
        return len(self._trades)

    def record_close(
        self,
        position: Position,
        *,
        exit_ts: int,
        exit_price: float,
        exit_bar_index: int,
        exit_commission: float,
        exit_slippage_cost: float,
    ) -> Trade:
        quantity = position.quantity
        bars_held = max(exit_bar_index - position.entry_bar_index, 1)
        if position.side is PositionSide.LONG:
            gross_pnl = round_money((exit_price - position.entry_price) * quantity)
        else:
            gross_pnl = round_money((position.entry_price - exit_price) * quantity)

        total_commission = round_money(position.entry_commission + exit_commission)
        total_slippage = round_money(position.entry_slippage_cost + exit_slippage_cost)
        net_pnl = round_money(gross_pnl - total_commission - total_slippage)

        trade = Trade(
            seq=self._next_seq,
            side=position.side,
            quantity=quantity,
            entry_ts=position.entry_ts,
            entry_price=position.entry_price,
            exit_ts=exit_ts,
            exit_price=exit_price,
            gross_pnl=gross_pnl,
            commission=total_commission,
            slippage_cost=total_slippage,
            net_pnl=net_pnl,
            bars_held=bars_held,
        )
        self._next_seq += 1
        self._trades.append(trade)
        return trade
