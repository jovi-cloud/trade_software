"""The bar loop with order execution at the next bar open."""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.domain.explain import ExplainLevel
from app.engine.bars import BarIterator
from app.engine.context import ExecutionContext, LogCollector
from app.engine.errors import StrategyCompileError
from app.engine.execution.order import Order
from app.engine.execution.order_book import OrderBook
from app.engine.execution.order_service import OrderService
from app.engine.execution.portfolio import PortfolioManager
from app.engine.execution.simulator import ExecutionSimulator, SimulatorConfig
from app.engine.execution.trade_manager import TradeManager
from app.engine.explain import ExplainCollector
from app.engine.explain.condition_collector import ConditionCollector
from app.engine.results.result import ExecutionResult
from app.engine.strategy.loader import StrategyLoader


@dataclass(frozen=True)
class ExecutionConfig:
    """Run configuration."""

    initial_capital: float = 100_000.0
    commission: float = 0.0
    slippage: float = 0.0
    explain_level: ExplainLevel = ExplainLevel.TRADES_ONLY
    instrument: str | None = None
    timeframe: str | None = None

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
        collector = (
            ExplainCollector(self.config.explain_level)
            if self.config.explain_level is not ExplainLevel.NONE
            else None
        )
        if collector is not None:
            collector.set_context(
                instrument=self.config.instrument,
                timeframe=self.config.timeframe,
            )
        if collector is not None:
            collector.record_run_started(bar_count=len(bar_list))
            collector.record_parameters_applied(
                initial_capital=self.config.initial_capital,
                commission=self.config.commission,
                slippage=self.config.slippage,
            )
            if bar_list:
                collector.set_clock(bar_list[0].ts)

        loader = StrategyLoader(logs)
        try:
            strategy = loader.load(strategy_source)
        except StrategyCompileError as exc:
            location = f" (line {exc.line})" if exc.line is not None else ""
            detail = f"{exc.message}{location}"
            if collector is not None:
                collector.record_strategy_load_failed(detail=detail)
                collector.record_run_completed(completed=False, trade_count=0)
            return self._result(
                completed=False,
                bars_processed=0,
                started=started,
                errors=[detail],
                warnings=warnings,
                logs=logs,
                portfolio=PortfolioManager(self.config.initial_capital),
                order_book=OrderBook(),
                trade_manager=TradeManager(),
                collector=collector,
            )

        if collector is not None:
            collector.record_strategy_loaded()

        if not strategy.defined_hooks:
            warnings.append(
                "Strategy defines none of on_start/on_bar/on_stop; the run will do nothing."
            )
        elif not strategy.defines_on_bar:
            warnings.append("Strategy defines no on_bar hook; bars were replayed but unused.")

        if len(bar_list) == 0:
            warnings.append("Dataset contains no bars; nothing was replayed.")

        portfolio = PortfolioManager(self.config.initial_capital)
        order_book = OrderBook()
        trade_manager = TradeManager()
        condition_collector = ConditionCollector() if collector is not None else None
        order_service = OrderService(order_book, portfolio, warnings, collector=collector)
        simulator = ExecutionSimulator(
            config=SimulatorConfig(
                commission=self.config.commission,
                slippage=self.config.slippage,
            ),
            portfolio=portfolio,
            trade_manager=trade_manager,
            order_book=order_book,
            warnings=warnings,
            collector=collector,
        )
        context = ExecutionContext(
            initial_capital=self.config.initial_capital,
            portfolio=portfolio,
            order_service=order_service,
            logs=logs,
            condition_collector=condition_collector,
        )
        strategy.bind_context(context)

        bars_processed = 0
        completed = True
        pending: list[Order] = []

        try:
            strategy.call_on_start()
        except Exception as exc:
            errors.append(f"on_start raised {type(exc).__name__}: {exc}")
            if collector is not None:
                collector.record_run_completed(completed=False, trade_count=0)
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
                collector=collector,
            )

        pending = order_book.take_pending()

        for index, bar in enumerate(bar_list):
            if collector is not None:
                collector.set_clock(bar.ts)
                collector.record_bar_processing_started(bar_index=index, timestamp_ms=bar.ts)
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
            if collector is not None and condition_collector is not None:
                condition_collector.add_inferred_condition(
                    "Already In Position",
                    actual="Yes" if portfolio.has_position else "No",
                    expected="No",
                    passed=not portfolio.has_position,
                )
                pending_count = order_book.pending_count
                condition_collector.add_inferred_condition(
                    "Pending Orders After Bar",
                    actual=str(pending_count),
                    expected="0",
                    passed=pending_count == 0,
                )
                snapshot = condition_collector.snapshot(bar_index=index)
                collector.record_conditions_evaluated(snapshot, timestamp_ms=bar.ts)
                condition_collector.clear()
            bars_processed += 1
            pending = order_book.take_pending()
            if collector is not None and portfolio.has_position:
                position = portfolio.position
                assert position is not None
                collector.observe_open_position(
                    bar_index=index,
                    timestamp_ms=bar.ts,
                    mark_price=bar.close,
                    cash=portfolio.cash,
                    side=position.side,
                    quantity=position.quantity,
                    entry_price=position.entry_price,
                )

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

        if collector is not None:
            collector.set_clock(bar_list[-1].ts if bar_list else collector.clock_ms)
            collector.record_run_completed(
                completed=completed,
                trade_count=trade_manager.trade_count,
            )

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
            collector=collector,
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
        collector: ExplainCollector | None,
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
            explain_events=collector.events if collector is not None else (),
            explain_level=self.config.explain_level,
        )
