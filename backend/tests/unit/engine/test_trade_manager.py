"""Trade P&L reconciliation tests."""

from __future__ import annotations

from app.domain.enums import PositionSide
from app.domain.money import round_money
from app.engine.execution.position import Position
from app.engine.execution.trade_manager import TradeManager


def test_net_pnl_reconciles_with_cash_for_long_with_slippage() -> None:
    manager = TradeManager()
    position = Position(
        side=PositionSide.LONG,
        quantity=10,
        entry_price=101.0,
        entry_ts=1,
        entry_bar_index=1,
        entry_commission=1.01,
        entry_slippage_cost=10.0,
    )
    trade = manager.record_close(
        position,
        exit_ts=2,
        exit_price=103.95,
        exit_bar_index=3,
        exit_commission=1.0395,
        exit_slippage_cost=11.0,
    )

    cash_delta = round_money((103.95 * 10 - 1.0395) - (101.0 * 10 + 1.01))
    assert trade.net_pnl == cash_delta
    assert trade.slippage_cost == 21.0
