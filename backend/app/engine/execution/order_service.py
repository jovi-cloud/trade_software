"""Strategy-facing order submission with single-position guardrails."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.domain.enums import OrderType
from app.engine.bars import Bar
from app.engine.execution.entry_window import entry_window_allows
from app.engine.execution.close_metadata import TradeCloseMetadata, metadata_from_risk_state
from app.engine.execution.order import Order
from app.engine.execution.order_book import OrderBook
from app.engine.execution.portfolio import PortfolioManager
from app.engine.explain.collector import ExplainCollector


class OrderService:
    """Accepts buy/sell/close requests from the execution context."""

    def __init__(
        self,
        order_book: OrderBook,
        portfolio: PortfolioManager,
        warnings: list[str],
        *,
        collector: ExplainCollector | None = None,
        session_timezone: str = "UTC",
        no_trade_session_dates: frozenset[str] | None = None,
        max_trades_per_day: int | None = None,
        entry_window_start: str | None = None,
        entry_window_end: str | None = None,
    ) -> None:
        self._order_book = order_book
        self._portfolio = portfolio
        self._warnings = warnings
        self._collector = collector
        self._current_bar_index = -1
        self._current_ts = 0
        self._session_timezone = ZoneInfo(session_timezone)
        self._no_trade_session_dates = no_trade_session_dates or frozenset()
        self._max_trades_per_day = max_trades_per_day
        self._entry_window_start = entry_window_start
        self._entry_window_end = entry_window_end
        self._entries_by_session_date: dict[str, int] = {}
        self._pending_close_metadata: TradeCloseMetadata | None = None

    def set_bar_context(self, *, bar_index: int, bar: Bar) -> None:
        self._current_bar_index = bar_index
        self._current_ts = bar.ts

    def buy(self, quantity: float = 1.0) -> Order | None:
        if blocked := self._entry_blocked_reason():
            return self._reject_entry(action="Buy", quantity=quantity, reason=blocked)
        if quantity <= 0:
            self._warnings.append("buy() ignored: quantity must be positive")
            return self._reject_entry(
                action="Buy",
                quantity=quantity,
                reason="quantity must be positive",
            )
        if self._portfolio.has_position:
            self._warnings.append(
                "buy() ignored: a position is already open; close it before opening another"
            )
            return self._reject_entry(
                action="Buy",
                quantity=quantity,
                reason="a position is already open",
            )
        order = self._order_book.submit(
            order_type=OrderType.BUY_MARKET,
            quantity=quantity,
            submitted_bar_index=self._current_bar_index,
            submitted_ts=self._current_ts,
        )
        self._record_signal(action="Buy", quantity=quantity, accepted=True)
        self._record_entry()
        if self._collector is not None:
            self._collector.record_order_created(order)
            self._collector.record_order_submitted(order)
        return order

    def sell(self, quantity: float = 1.0) -> Order | None:
        if blocked := self._entry_blocked_reason():
            return self._reject_entry(action="Sell short", quantity=quantity, reason=blocked)
        if quantity <= 0:
            self._warnings.append("sell() ignored: quantity must be positive")
            return self._reject_entry(
                action="Sell short",
                quantity=quantity,
                reason="quantity must be positive",
            )
        if self._portfolio.has_position:
            self._warnings.append(
                "sell() ignored: a position is already open; close it before opening another"
            )
            return self._reject_entry(
                action="Sell short",
                quantity=quantity,
                reason="a position is already open",
            )
        order = self._order_book.submit(
            order_type=OrderType.SELL_MARKET,
            quantity=quantity,
            submitted_bar_index=self._current_bar_index,
            submitted_ts=self._current_ts,
        )
        self._record_signal(action="Sell short", quantity=quantity, accepted=True)
        self._record_entry()
        if self._collector is not None:
            self._collector.record_order_created(order)
            self._collector.record_order_submitted(order)
        return order

    def close(
        self,
        *,
        exit_reason: str | None = None,
        risk_state: object | None = None,
    ) -> Order | None:
        if not self._portfolio.has_position:
            self._warnings.append("close() ignored: no open position")
            self._record_signal(
                action="Close",
                quantity=0,
                accepted=False,
                rejection_reason="no open position",
            )
            return None
        from app.engine.strategy.risk import TradeRiskState

        self._pending_close_metadata = metadata_from_risk_state(
            risk_state if isinstance(risk_state, TradeRiskState) else None,
            exit_reason=exit_reason or "close",
        )
        position = self._portfolio.position
        assert position is not None
        order = self._order_book.submit(
            order_type=OrderType.CLOSE,
            quantity=position.quantity,
            submitted_bar_index=self._current_bar_index,
            submitted_ts=self._current_ts,
        )
        self._record_signal(action="Close", quantity=position.quantity, accepted=True)
        if self._collector is not None:
            self._collector.record_order_created(order)
            self._collector.record_order_submitted(order)
        return order

    def consume_close_metadata(self) -> TradeCloseMetadata | None:
        metadata = self._pending_close_metadata
        self._pending_close_metadata = None
        return metadata

    def _session_date(self) -> str:
        local = datetime.fromtimestamp(self._current_ts / 1000, tz=UTC).astimezone(
            self._session_timezone
        )
        return local.strftime("%Y-%m-%d")

    def _minutes_into_day(self) -> int:
        local = datetime.fromtimestamp(self._current_ts / 1000, tz=UTC).astimezone(
            self._session_timezone
        )
        return local.hour * 60 + local.minute

    def _entry_blocked_reason(self) -> str | None:
        session_date = self._session_date()
        if session_date in self._no_trade_session_dates:
            return f"new entries disabled on {session_date} (price anomaly day)"
        if self._max_trades_per_day is not None:
            taken = self._entries_by_session_date.get(session_date, 0)
            if taken >= self._max_trades_per_day:
                return (
                    f"daily entry limit reached on {session_date} "
                    f"({self._max_trades_per_day} max)"
                )
        if self._entry_window_start is not None and self._entry_window_end is not None:
            local_time = datetime.fromtimestamp(self._current_ts / 1000, tz=UTC).astimezone(
                self._session_timezone
            )
            current = f"{local_time.hour:02d}:{local_time.minute:02d}"
            if not entry_window_allows(
                minutes_into_day=self._minutes_into_day(),
                start=self._entry_window_start,
                end=self._entry_window_end,
            ):
                return (
                    "new entries disabled outside the configured trading window "
                    f"({self._entry_window_start}–{self._entry_window_end} exchange time; "
                    f"now {current})"
                )
        return None

    def _record_entry(self) -> None:
        if self._max_trades_per_day is None:
            return
        session_date = self._session_date()
        self._entries_by_session_date[session_date] = (
            self._entries_by_session_date.get(session_date, 0) + 1
        )

    def _reject_entry(self, *, action: str, quantity: float, reason: str) -> None:
        self._warnings.append(f"{action.lower()}() ignored: {reason}")
        self._record_signal(
            action=action,
            quantity=quantity,
            accepted=False,
            rejection_reason=reason,
        )
        return None

    def _record_signal(
        self,
        *,
        action: str,
        quantity: float,
        accepted: bool,
        rejection_reason: str | None = None,
    ) -> None:
        if self._collector is None:
            return
        self._collector.record_signal_generated(
            action=action,
            quantity=quantity,
            bar_index=self._current_bar_index,
            timestamp_ms=self._current_ts,
            accepted=accepted,
            rejection_reason=rejection_reason,
        )
