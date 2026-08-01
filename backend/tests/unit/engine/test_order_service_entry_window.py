"""Tests for entry-window blocking in the order service."""

from __future__ import annotations

from app.engine.bars import Bar
from app.engine.execution.order_book import OrderBook
from app.engine.execution.order_service import OrderService
from app.engine.execution.portfolio import PortfolioManager


def _ts(iso_local: str) -> int:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    dt = datetime.fromisoformat(iso_local).replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    return int(dt.timestamp() * 1000)


def _bar(iso_local: str) -> Bar:
    return Bar(
        ts=_ts(iso_local),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1.0,
    )


def test_buy_blocked_outside_entry_window() -> None:
    warnings: list[str] = []
    portfolio = PortfolioManager(100_000.0)
    order_book = OrderBook()
    service = OrderService(
        order_book,
        portfolio,
        warnings,
        session_timezone="Asia/Kolkata",
        entry_window_start="09:15",
        entry_window_end="15:25",
    )
    service.set_bar_context(bar_index=0, bar=_bar("2024-01-02 08:45:00"))
    assert service.buy(1.0) is None

    service.set_bar_context(bar_index=1, bar=_bar("2024-01-02 09:15:00"))
    assert service.buy(1.0) is not None


def test_close_still_allowed_outside_entry_window() -> None:
    warnings: list[str] = []
    portfolio = PortfolioManager(100_000.0)
    bar = _bar("2024-01-02 16:00:00")
    portfolio.open_long(
        quantity=1.0,
        fill_price=100.0,
        fill_ts=bar.ts,
        entry_bar_index=0,
        commission=0.0,
        slippage_cost=0.0,
    )
    order_book = OrderBook()
    service = OrderService(
        order_book,
        portfolio,
        warnings,
        session_timezone="Asia/Kolkata",
        entry_window_start="09:15",
        entry_window_end="15:25",
    )
    service.set_bar_context(bar_index=0, bar=bar)

    order = service.close()
    assert order is not None
    assert not warnings
