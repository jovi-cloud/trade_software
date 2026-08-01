"""The bar loop with order execution at the next bar open."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from itertools import chain

from app.domain.decisions import DecisionSchema, DecisionSink
from app.domain.explain import ExplainLevel
from app.engine.bars import BarIterator
from app.engine.context import ExecutionContext, LogCollector
from app.engine.errors import EngineError, StrategyCompileError
from app.engine.execution.order import Order
from app.engine.execution.order_book import OrderBook
from app.engine.execution.order_service import OrderService
from app.engine.execution.portfolio import PortfolioManager
from app.engine.execution.simulator import ExecutionSimulator, SimulatorConfig
from app.engine.execution.trade_manager import TradeManager
from app.engine.explain import MAX_PER_BAR_EXPLAIN_EVENTS, ExplainCollector
from app.engine.explain.condition_collector import ConditionCollector
from app.engine.explain.decision_log import DecisionRecorder
from app.engine.results.chart_data import TrailingStopCollector
from app.engine.results.result import ExecutionResult
from app.engine.strategy.risk import StopLossOverride
from app.engine.strategy.provider import SourceStrategyProvider, StrategyProvider


@dataclass(frozen=True)
class ExecutionConfig:
    """Run configuration."""

    initial_capital: float = 100_000.0
    commission: float = 0.0
    slippage: float = 0.0
    explain_level: ExplainLevel = ExplainLevel.TRADES_ONLY
    instrument: str | None = None
    timeframe: str | None = None
    session_timezone: str = "UTC"
    no_trade_session_dates: frozenset[str] = frozenset()
    #: Cap new entries per exchange-local session day. ``None`` means unlimited.
    max_trades_per_day: int | None = None
    #: Inclusive exchange-local entry window. Both must be set together.
    entry_window_start: str | None = None
    entry_window_end: str | None = None
    stop_loss_override: StopLossOverride | None = None

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be greater than zero")
        if self.commission < 0:
            raise ValueError("commission must not be negative")
        if self.slippage < 0:
            raise ValueError("slippage must not be negative")
        if self.max_trades_per_day is not None and self.max_trades_per_day < 1:
            raise ValueError("max_trades_per_day must be at least 1 when set")
        from app.engine.execution.entry_window import validate_entry_window

        window = validate_entry_window(self.entry_window_start, self.entry_window_end)
        if window is not None:
            object.__setattr__(self, "entry_window_start", window[0])
            object.__setattr__(self, "entry_window_end", window[1])


class ExecutionEngine:
    """Replays a dataset through a strategy with simulated market fills."""

    def __init__(self, config: ExecutionConfig | None = None) -> None:
        self.config = config or ExecutionConfig()

    def run(
        self,
        *,
        bars: BarIterator,
        strategy_source: str | None = None,
        strategy: StrategyProvider | None = None,
        on_progress: Callable[[int, int], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
        decision_sink: DecisionSink | None = None,
    ) -> ExecutionResult:
        """Replay ``bars`` through a strategy.

        Pass ``strategy_source`` for user-authored code (the original and still
        the default path) or ``strategy`` for any other provider - a library
        strategy, for instance. Exactly one is required. Everything after the
        strategy is obtained is identical either way: same bar loop, same fill
        timing, same portfolio, same metrics.

        ``decision_sink`` receives one row per bar carrying every indicator
        value, condition verdict and calculation operand. Rows are streamed as
        they are produced, so the log is uncapped regardless of bar count - the
        engine never holds it. Supplying a sink also stops per-bar conditions
        being duplicated into the JSON explain events, which is what previously
        forced them to be truncated past 50,000 bars.
        """
        if (strategy_source is None) == (strategy is None):
            raise EngineError("Provide exactly one of strategy_source or strategy")
        provider: StrategyProvider = (
            strategy if strategy is not None else SourceStrategyProvider(strategy_source or "")
        )

        started = time.perf_counter()
        logs = LogCollector()
        errors: list[str] = []
        warnings: list[str] = []
        total_bars = len(bars)
        # Replayed one bar at a time. A streamed source is never materialised,
        # which is what keeps a multi-million-bar dataset from costing gigabytes
        # before the first bar is even processed. The first bar is pulled early
        # only to date the events recorded before the loop starts, then pushed
        # back on the front - the loop still sees every bar exactly once.
        bar_stream = iter(bars)
        first_bar = next(bar_stream, None)
        if first_bar is not None:
            bar_stream = chain((first_bar,), bar_stream)
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
        recorder = (
            DecisionRecorder(
                decision_sink,
                instrument=self.config.instrument,
                timeframe=self.config.timeframe,
            )
            if decision_sink is not None
            else None
        )
        if collector is not None:
            collector.record_run_started(bar_count=total_bars)
            collector.record_parameters_applied(
                initial_capital=self.config.initial_capital,
                commission=self.config.commission,
                slippage=self.config.slippage,
            )
            if first_bar is not None:
                collector.set_clock(first_bar.ts)

        try:
            loaded = provider.load(logs)
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
                recorder=recorder,
            )

        if collector is not None:
            collector.record_strategy_loaded()

        if not loaded.defined_hooks:
            warnings.append(
                "Strategy defines none of on_start/on_bar/on_stop; the run will do nothing."
            )
        elif not loaded.defines_on_bar:
            warnings.append("Strategy defines no on_bar hook; bars were replayed but unused.")

        if total_bars == 0:
            warnings.append("Dataset contains no bars; nothing was replayed.")

        portfolio = PortfolioManager(self.config.initial_capital)
        order_book = OrderBook()
        trade_manager = TradeManager()
        # Condition traces feed the Decision Inspector, via the decision log when
        # there is one and via FULL-level explain events otherwise. With neither,
        # collecting them costs a snapshot per bar and nothing reads the result.
        condition_collector = (
            ConditionCollector()
            if recorder is not None or (collector is not None and collector.records_bar_events)
            else None
        )
        order_service = OrderService(
            order_book,
            portfolio,
            warnings,
            collector=collector,
            session_timezone=self.config.session_timezone,
            no_trade_session_dates=self.config.no_trade_session_dates,
            max_trades_per_day=self.config.max_trades_per_day,
            entry_window_start=self.config.entry_window_start,
            entry_window_end=self.config.entry_window_end,
        )
        simulator = ExecutionSimulator(
            config=SimulatorConfig(
                commission=self.config.commission,
                slippage=self.config.slippage,
            ),
            portfolio=portfolio,
            trade_manager=trade_manager,
            order_book=order_book,
            order_service=order_service,
            warnings=warnings,
            collector=collector,
        )
        trailing_stop_collector = TrailingStopCollector()
        context = ExecutionContext(
            initial_capital=self.config.initial_capital,
            portfolio=portfolio,
            order_service=order_service,
            logs=logs,
            condition_collector=condition_collector,
            stop_loss_override=self.config.stop_loss_override,
            trailing_stop_collector=trailing_stop_collector,
            trade_manager=trade_manager,
        )
        loaded.bind_context(context)

        bars_processed = 0
        completed = True
        pending: list[Order] = []

        try:
            loaded.call_on_start()
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
                recorder=recorder,
            )

        pending = order_book.take_pending()

        last_ts = first_bar.ts if first_bar is not None else 0
        for index, bar in enumerate(bar_stream):
            last_ts = bar.ts
            if should_cancel is not None and should_cancel():
                warnings.append("Backtest was cancelled before completion.")
                completed = False
                break
            if collector is not None:
                collector.set_clock(bar.ts)
            if pending:
                simulator.fill_pending(pending, bar, index)
                pending = []

            context.advance_to(bar, bar_index=index)
            try:
                loaded.call_on_bar(bar)
            except Exception as exc:
                errors.append(
                    f"on_bar raised {type(exc).__name__} at bar {index} "
                    f"({bar.timestamp.isoformat()}): {exc}"
                )
                completed = False
                break
            if condition_collector is not None:
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
                if recorder is not None:
                    recorder.record(snapshot, bar=bar, bar_index=index)
                # Once the decision log owns the per-bar record, echoing it into
                # the JSON events buys nothing and costs ~1.6 KB per bar - which
                # is what made the events need a cap in the first place.
                elif collector is not None:
                    collector.record_conditions_evaluated(snapshot, timestamp_ms=bar.ts)
                condition_collector.clear()
            bars_processed += 1
            if on_progress is not None and (
                bars_processed == total_bars or bars_processed % 50 == 0
            ):
                on_progress(bars_processed, total_bars)
            if bars_processed % 100 == 0:
                time.sleep(0)
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
                loaded.call_on_stop()
            except Exception as exc:
                errors.append(f"on_stop raised {type(exc).__name__}: {exc}")
                completed = False

        if collector is not None:
            collector.set_clock(last_ts if total_bars else collector.clock_ms)
            if collector.dropped_event_count and recorder is None:
                warnings.append(
                    f"Explainability log truncated: {collector.dropped_event_count:,} per-bar "
                    f"events were dropped after the first {MAX_PER_BAR_EXPLAIN_EVENTS:,}. "
                    "Trades, orders and metrics are complete; run a shorter date range for "
                    "a full bar-by-bar decision log."
                )
            elif collector.dropped_event_count:
                # The decision log is complete, so this is no longer a gap in the
                # record - only in the mark-to-market events the timeline draws.
                warnings.append(
                    f"{collector.dropped_event_count:,} per-bar mark-to-market events were "
                    f"dropped after the first {MAX_PER_BAR_EXPLAIN_EVENTS:,}. The bar-by-bar "
                    "decision log is complete and unaffected."
                )
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
            recorder=recorder,
            trailing_stop_collector=trailing_stop_collector,
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
        recorder: DecisionRecorder | None = None,
        trailing_stop_collector: TrailingStopCollector | None = None,
    ) -> ExecutionResult:
        # Every return path in ``run`` funnels through here, which is what makes
        # this the one place guaranteed to close the sink - including the early
        # returns for a compile failure or a raising ``on_start``.
        decision_schema: DecisionSchema | None = None
        decision_rows = 0
        if recorder is not None:
            decision_rows = recorder.rows
            decision_schema = recorder.finish()
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
            decision_schema=decision_schema,
            decision_rows=decision_rows,
            trailing_stop_points=(
                trailing_stop_collector.points if trailing_stop_collector is not None else ()
            ),
        )
