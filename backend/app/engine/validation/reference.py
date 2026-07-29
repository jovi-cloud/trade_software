"""Interfaces for comparing engine output against external reference engines.

No external engines are integrated in Phase 4C. These protocols define the seam
so Backtrader, VectorBT, Zipline, or TradingView exports can plug in later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.engine.bars import Bar
from app.engine.results.result import ExecutionResult
from app.engine.runner import ExecutionConfig


@dataclass(frozen=True)
class ReferenceScenario:
    """Inputs shared between the internal engine and a reference adapter."""

    name: str
    strategy_source: str
    bars: tuple[Bar, ...]
    config: ExecutionConfig


@dataclass(frozen=True)
class ReferenceTrade:
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    net_pnl: float


@dataclass(frozen=True)
class ReferenceRunResult:
    engine_name: str
    final_cash: float
    trade_count: int
    trades: tuple[ReferenceTrade, ...]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ReferenceComparison:
    scenario_name: str
    reference_engine: str
    matched: bool
    differences: tuple[str, ...]


class ReferenceEngineAdapter(Protocol):
    """External backtest engine that can replay a ``ReferenceScenario``."""

    name: str

    def run(self, scenario: ReferenceScenario) -> ReferenceRunResult:
        """Execute the scenario and return comparable trade-level output."""


class ReferenceComparator(Protocol):
    """Compare an internal ``ExecutionResult`` with a reference run."""

    def compare(
        self,
        *,
        scenario_name: str,
        internal: ExecutionResult,
        reference: ReferenceRunResult,
        tolerance: float = 1e-6,
    ) -> ReferenceComparison:
        """Return field-level differences between internal and reference output."""
