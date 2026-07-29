"""The bar loop with order execution at the next bar open."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.engine.bars import BarIterator
from app.engine.context import ExecutionContext, LogCollector
from app.engine.errors import StrategyCompileError
from app.engine.execution.order import Order
from app.engine.execution.order_book import OrderBook
from app.engine.execution.order_service import OrderService
from app.engine.execution.portfolio import PortfolioManager
from app.engine.execution.simulator import ExecutionSimulator, SimulatorConfig
from app.engine.execution.trade_manager import TradeManager
from app.engine.results.result import ExecutionResult
from app.engine.strategy.loader import StrategyLoader


@dataclass(frozen=True)
class ExecutionConfig:
    """Run configuration."""

    initial_capital: float = 100_000.0
    commission: float = 0.0
    slippage: float = 0.0

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be greater than zero")
        if self.commission < 0:
            raise ValueError("commission must not be negative")
        if self.slippage < 0:
            raise ValueError("slippage must not be negative")


class ExecutionEngine:
    """Replays a dataset through a strategy with simulated market fills."""

    def __init__(self, config: ExecutionConfig | None = None) -> None:
        self.config = config or ExecutionConfig()

    def run(self, *, strategy_source: str, bars: BarIterator) -> ExecutionResult:
        started = time.perf_counter()
        logs = LogCollector()
        errors: list[str] = []
        warnings: list[str] = []
        bar_list = list(bars)

        if len(bar_list) == 0:
            warnings.append("Dataset contains no bars; nothing was replayed.")

        loader = StrategyLoader(logs)
        try:
            strategy = loader.load(strategy_source)
        except StrategyCompileError as exc:
            location = f" (line {exc.line})" if exc.line is not None else ""
            return self._result(
                completed=False,
                bars_processed=0,
                started=started,
                errors=[f"{exc.message}{location}"],
                warnings=warnings,
                logs=logs,
                portfolio=PortfolioManager(self.config.initial_capital),
                order_book=OrderBook(),
                trade_manager=TradeManager(),
            )

        if not strategy.defined_hooks:
            warnings.append(
                "Strategy defines none of on_start/on_bar/on_stop; the run will do nothing."
            )
        elif not strategy.defines_on_bar:
            warnings.append("Strategy defines no on_bar hook; bars were replayed but unused.")

        portfolio = PortfolioManager(self.config.initial_capital)
        order_book = OrderBook()
        trade_manager = TradeManager()
        order_service = OrderService(order_book, portfolio, warnings)
        simulator = ExecutionSimulator(
            config=SimulatorConfig(
                commission=self.config.commission,
                slippage=self.config.slippage,
            ),
            portfolio=portfolio,
            trade_manager=trade_manager,
            order_book=order_book,
            warnings=warnings,
        )
        context = ExecutionContext(
            initial_capital=self.config.initial_capital,
            portfolio=portfolio,
            order_service=order_service,
            logs=logs,
        )
        strategy.bind_context(context)

        bars_processed = 0
        completed = True
        pending: list[Order] = []

        try:
            strategy.call_on_start()
        except Exception as exc:
            errors.append(f"on_start raised {type(exc).__name__}: {exc}")
            return self._result(
                completed=False,
                bars_processed=0,
                started=started,
                errors=errors,
                warnings=warnings,
                logs=logs,
                portfolio=portfolio,
                order_book=order_book,
                trade_manager=trade_manager,
            )

        pending = order_book.take_pending()

        for index, bar in enumerate(bar_list):
            if pending:
                simulator.fill_pending(pending, bar, index)
                pending = []

            context.advance_to(bar, bar_index=index)
            try:
                strategy.call_on_bar(bar)
            except Exception as exc:
                errors.append(
                    f"on_bar raised {type(exc).__name__} at bar {index} "
                    f"({bar.timestamp.isoformat()}): {exc}"
                )
                completed = False
                break
            bars_processed += 1
            pending = order_book.take_pending()

        if pending:
            warnings.append(
                f"{len(pending)} order(s) were not filled because the dataset ended "
                "before the next bar open."
            )

        if completed:
            try:
                strategy.call_on_stop()
            except Exception as exc:
                errors.append(f"on_stop raised {type(exc).__name__}: {exc}")
                completed = False

        return self._result(
            completed=completed,
            bars_processed=bars_processed,
            started=started,
            errors=errors,
            warnings=warnings,
            logs=logs,
            portfolio=portfolio,
            order_book=order_book,
            trade_manager=trade_manager,
        )

    def _result(
        self,
        *,
        completed: bool,
        bars_processed: int,
        started: float,
        errors: list[str],
        warnings: list[str],
        logs: LogCollector,
        portfolio: PortfolioManager,
        order_book: OrderBook,
        trade_manager: TradeManager,
    ) -> ExecutionResult:
        if logs.truncated:
            warnings = [
                *warnings,
                "Strategy log output was truncated; only the first entries are shown.",
            ]
        if portfolio.has_position:
            warnings.append("Run ended with an open position; it was not auto-closed.")

        return ExecutionResult(
            completed=completed,
            bars_processed=bars_processed,
            execution_time_ms=round((time.perf_counter() - started) * 1000, 3),
            errors=tuple(errors),
            warnings=tuple(warnings),
            strategy_logs=logs.entries,
            orders=order_book.history,
            trades=trade_manager.trades,
            final_cash=portfolio.cash,
            position_closed=not portfolio.has_position,
            trade_count=trade_manager.trade_count,
        )
