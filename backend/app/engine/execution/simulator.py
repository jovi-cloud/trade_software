"""Fill pending market orders at the next bar open."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import OrderStatus, OrderType, PositionSide
from app.domain.money import mul_money, round_money, round_price
from app.engine.bars import Bar
from app.engine.execution.order import Order
from app.engine.execution.order_book import OrderBook
from app.engine.execution.portfolio import PortfolioManager
from app.engine.execution.trade_manager import TradeManager
from app.engine.explain.collector import ExplainCollector


@dataclass(frozen=True)
class SimulatorConfig:
    commission: float
    slippage: float


class ExecutionSimulator:
    """Matches pending orders against a bar's open price."""

    def __init__(
        self,
        *,
        config: SimulatorConfig,
        portfolio: PortfolioManager,
        trade_manager: TradeManager,
        order_book: OrderBook,
        warnings: list[str],
        collector: ExplainCollector | None = None,
    ) -> None:
        self._config = config
        self._portfolio = portfolio
        self._trade_manager = trade_manager
        self._order_book = order_book
        self._warnings = warnings
        self._collector = collector

    def fill_pending(self, orders: list[Order], bar: Bar, bar_index: int) -> None:
        for order in orders:
            self._fill_one(order, bar, bar_index)

    def _fill_one(self, order: Order, bar: Bar, bar_index: int) -> None:
        if order.order_type is OrderType.BUY_MARKET:
            self._fill_buy_market(order, bar, bar_index)
        elif order.order_type is OrderType.SELL_MARKET:
            self._fill_sell_market(order, bar, bar_index)
        elif order.order_type is OrderType.CLOSE:
            self._fill_close(order, bar, bar_index)

    def _fill_buy_market(self, order: Order, bar: Bar, bar_index: int) -> None:
        if self._portfolio.has_position:
            self._order_book.mark_rejected(order, "Position already open")
            self._warnings.append(f"Order {order.id} rejected: position already open")
            self._record_rejection(order)
            return

        fill_price = round_price(bar.open * (1 + self._config.slippage))
        slippage_cost = round_money(mul_money(order.quantity, bar.open * self._config.slippage))
        commission = round_money(mul_money(order.quantity * fill_price, self._config.commission))
        total_cost = round_money(mul_money(order.quantity, fill_price) + commission)

        if total_cost > self._portfolio.cash:
            self._order_book.mark_rejected(order, "Insufficient cash")
            self._warnings.append(f"Order {order.id} rejected: insufficient cash")
            self._record_rejection(order)
            return

        self._portfolio.open_long(
            quantity=order.quantity,
            fill_price=fill_price,
            fill_ts=bar.ts,
            entry_bar_index=bar_index,
            commission=commission,
            slippage_cost=slippage_cost,
        )
        self._mark_filled(order, bar, bar_index, fill_price, commission, slippage_cost)
        if self._collector is not None:
            self._collector.record_position_opened(
                side=PositionSide.LONG,
                quantity=order.quantity,
                price=fill_price,
                bar_index=bar_index,
                timestamp_ms=bar.ts,
                order_id=order.id,
                cash=self._portfolio.cash,
                portfolio_value=self._portfolio_value(fill_price),
            )

    def _fill_sell_market(self, order: Order, bar: Bar, bar_index: int) -> None:
        if self._portfolio.has_position:
            self._order_book.mark_rejected(order, "Position already open")
            self._warnings.append(f"Order {order.id} rejected: position already open")
            self._record_rejection(order)
            return

        fill_price = round_price(bar.open * (1 - self._config.slippage))
        slippage_cost = round_money(mul_money(order.quantity, bar.open * self._config.slippage))
        commission = round_money(mul_money(order.quantity * fill_price, self._config.commission))

        self._portfolio.open_short(
            quantity=order.quantity,
            fill_price=fill_price,
            fill_ts=bar.ts,
            entry_bar_index=bar_index,
            commission=commission,
            slippage_cost=slippage_cost,
        )
        self._mark_filled(order, bar, bar_index, fill_price, commission, slippage_cost)
        if self._collector is not None:
            self._collector.record_position_opened(
                side=PositionSide.SHORT,
                quantity=order.quantity,
                price=fill_price,
                bar_index=bar_index,
                timestamp_ms=bar.ts,
                order_id=order.id,
                cash=self._portfolio.cash,
                portfolio_value=self._portfolio_value(fill_price),
            )

    def _fill_close(self, order: Order, bar: Bar, bar_index: int) -> None:
        position = self._portfolio.position
        if position is None:
            self._order_book.mark_rejected(order, "No open position")
            self._warnings.append(f"Order {order.id} rejected: no open position")
            self._record_rejection(order)
            return

        if position.side is PositionSide.LONG:
            fill_price = round_price(bar.open * (1 - self._config.slippage))
            slippage_cost = round_money(
                mul_money(position.quantity, bar.open * self._config.slippage)
            )
            commission = round_money(
                mul_money(position.quantity * fill_price, self._config.commission)
            )
            proceeds = round_money(mul_money(position.quantity, fill_price) - commission)
            self._portfolio.credit_cash(proceeds)
        else:
            fill_price = round_price(bar.open * (1 + self._config.slippage))
            slippage_cost = round_money(
                mul_money(position.quantity, bar.open * self._config.slippage)
            )
            commission = round_money(
                mul_money(position.quantity * fill_price, self._config.commission)
            )
            cost = round_money(mul_money(position.quantity, fill_price) + commission)
            self._portfolio.debit_cash(cost)

        closed_side = position.side
        closed_quantity = position.quantity
        closed = self._portfolio.close_position()
        trade = self._trade_manager.record_close(
            closed,
            exit_ts=bar.ts,
            exit_price=fill_price,
            exit_bar_index=bar_index,
            exit_commission=commission,
            exit_slippage_cost=slippage_cost,
        )
        self._mark_filled(order, bar, bar_index, fill_price, commission, slippage_cost)
        if self._collector is not None:
            self._collector.record_position_closed(
                side=closed_side,
                quantity=closed_quantity,
                price=fill_price,
                bar_index=bar_index,
                timestamp_ms=bar.ts,
                order_id=order.id,
                trade_seq=trade.seq,
                cash=self._portfolio.cash,
                portfolio_value=self._portfolio.cash,
            )
            self._collector.record_profit_calculated(
                trade,
                cash=self._portfolio.cash,
                portfolio_value=self._portfolio.cash,
            )

    def _mark_filled(
        self,
        order: Order,
        bar: Bar,
        bar_index: int,
        fill_price: float,
        commission: float,
        slippage_cost: float,
    ) -> None:
        order.status = OrderStatus.FILLED
        order.fill_price = fill_price
        order.fill_ts = bar.ts
        order.filled_bar_index = bar_index
        order.commission = commission
        order.slippage_cost = slippage_cost
        if self._collector is not None:
            self._collector.record_order_filled(
                order,
                cash=self._portfolio.cash,
                portfolio_value=self._portfolio_value(fill_price),
            )

    def _record_rejection(self, order: Order) -> None:
        if self._collector is not None:
            self._collector.record_order_rejected(order)

    def _portfolio_value(self, mark_price: float) -> float:
        position = self._portfolio.position
        if position is None:
            return self._portfolio.cash
        if position.side is PositionSide.LONG:
            return round_money(
                self._portfolio.cash + mul_money(position.quantity, mark_price)
            )
        return self._portfolio.cash
