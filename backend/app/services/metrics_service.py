"""Compute performance metrics from execution results."""

from __future__ import annotations

from dataclasses import replace

from app.engine.results.metrics import MetricsEngine
from app.engine.results.metrics_result import EquityPoint, PerformanceMetrics
from app.engine.results.result import ExecutionResult


class MetricsService:
    """Attaches performance analytics to a completed execution result."""

    def __init__(self, engine: MetricsEngine | None = None) -> None:
        self.engine = engine or MetricsEngine()

    def enrich(
        self, result: ExecutionResult, *, initial_capital: float
    ) -> ExecutionResult:
        metrics, equity_history = self.engine.compute(
            trades=result.trades,
            initial_capital=initial_capital,
            final_cash=result.final_cash,
        )
        return replace(result, metrics=metrics, equity_history=equity_history)

    def compute(
        self, result: ExecutionResult, *, initial_capital: float
    ) -> tuple[PerformanceMetrics, tuple[EquityPoint, ...]]:
        return self.engine.compute(
            trades=result.trades,
            initial_capital=initial_capital,
            final_cash=result.final_cash,
        )
