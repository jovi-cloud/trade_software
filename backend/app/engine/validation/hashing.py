"""Deterministic hashing of execution results for consistency checks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any

from app.engine.results.metrics import MetricsEngine
from app.engine.results.result import ExecutionResult


def _canonicalize(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, tuple):
        return [_canonicalize(item) for item in value]
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


def hash_execution_result(result: ExecutionResult, *, initial_capital: float) -> str:
    """SHA-256 digest of trades, metrics, and equity for determinism checks."""
    metrics, equity = MetricsEngine().compute(
        trades=list(result.trades),
        initial_capital=initial_capital,
        final_cash=result.final_cash,
    )
    payload = {
        "completed": result.completed,
        "bars_processed": result.bars_processed,
        "trade_count": result.trade_count,
        "final_cash": result.final_cash,
        "position_closed": result.position_closed,
        "trades": _canonicalize(result.trades),
        "metrics": asdict(metrics),
        "equity_history": _canonicalize(equity),
        "entry_markers_count": len(result.entry_markers),
        "exit_markers_count": len(result.exit_markers),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()
