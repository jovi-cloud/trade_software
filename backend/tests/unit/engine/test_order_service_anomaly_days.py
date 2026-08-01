"""Tests for blocking new entries on price-anomaly session days."""

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


def test_buy_blocked_on_no_trade_session_date() -> None:
    warnings: list[str] = []
    portfolio = PortfolioManager(100_000.0)
    order_book = OrderBook()
    service = OrderService(
        order_book,
        portfolio,
        warnings,
        session_timezone="Asia/Kolkata",
        no_trade_session_dates=frozenset({"2024-01-02"}),
    )
    bar = Bar(
        ts=_ts("2024-01-02 09:15:00"),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1.0,
    )
    service.set_bar_context(bar_index=0, bar=bar)

    assert service.buy(1.0) is None
    assert order_book.pending_count == 0
    assert any("price anomaly day" in warning for warning in warnings)


def test_close_still_allowed_on_no_trade_session_date() -> None:
    warnings: list[str] = []
    portfolio = PortfolioManager(100_000.0)
    bar = Bar(
        ts=_ts("2024-01-02 09:15:00"),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1.0,
    )
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
        no_trade_session_dates=frozenset({"2024-01-02"}),
    )
    service.set_bar_context(bar_index=0, bar=bar)

    order = service.close()
    assert order is not None
    assert order_book.pending_count == 1
    assert not warnings
