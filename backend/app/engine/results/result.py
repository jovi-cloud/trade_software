"""The result of one replay including orders, trades, and performance."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.engine.execution.order import Order
from app.engine.execution.trade import Trade
from app.engine.results.chart_data import Candle, TradeMarker
from app.engine.results.metrics_result import EquityPoint, PerformanceMetrics


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome of replaying a dataset through a strategy."""

    # False when the run stopped early: compile failure, or a hook raised.
    completed: bool
    bars_processed: int
    execution_time_ms: float
    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    strategy_logs: tuple[str, ...] = field(default_factory=tuple)
    orders: tuple[Order, ...] = field(default_factory=tuple)
    trades: tuple[Trade, ...] = field(default_factory=tuple)
    final_cash: float = 0.0
    position_closed: bool = True
    trade_count: int = 0
    metrics: PerformanceMetrics | None = None
    equity_history: tuple[EquityPoint, ...] = field(default_factory=tuple)
    candles: tuple[Candle, ...] = field(default_factory=tuple)
    entry_markers: tuple[TradeMarker, ...] = field(default_factory=tuple)
    exit_markers: tuple[TradeMarker, ...] = field(default_factory=tuple)
