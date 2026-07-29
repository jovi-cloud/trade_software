"""Backtest engine.

Framework-free by contract: imports nothing from FastAPI, SQLAlchemy or
Pydantic, and nothing from app.api / app.services / app.models / app.db.
Enforced by the import-linter contracts in pyproject.toml.

Usable standalone - bars in, result out, no database and no web server::

    from app.engine import Bar, BarIterator, ExecutionConfig, ExecutionEngine

    bars = BarIterator([Bar(ts=0, open=1, high=2, low=0.5, close=1.5, volume=10)])
    result = ExecutionEngine(ExecutionConfig()).run(
        strategy_source=(
            "class Strategy:\\n    def on_bar(self, bar):\\n        self.ctx.log(bar.close)\\n"
        ),
        bars=bars,
    )
"""

from app.engine.bars import Bar, BarIterator
from app.engine.context import Context, ExecutionContext, LogCollector
from app.engine.errors import EngineError, StrategyCompileError, StrategyRuntimeError
from app.engine.results.metrics import MetricsEngine
from app.engine.results.metrics_result import EquityPoint, PerformanceMetrics
from app.engine.results.result import ExecutionResult
from app.engine.runner import ExecutionConfig, ExecutionEngine
from app.engine.strategy.base import LoadedStrategy, Strategy
from app.engine.strategy.loader import StrategyLoader

__all__ = [
    "Bar",
    "BarIterator",
    "Context",
    "EngineError",
    "EquityPoint",
    "ExecutionConfig",
    "ExecutionContext",
    "ExecutionEngine",
    "ExecutionResult",
    "LoadedStrategy",
    "LogCollector",
    "MetricsEngine",
    "PerformanceMetrics",
    "Strategy",
    "StrategyCompileError",
    "StrategyLoader",
    "StrategyRuntimeError",
]
