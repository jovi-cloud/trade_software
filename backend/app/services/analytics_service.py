"""The seam between the engine's output and the analytics layer.

Neither side knows about the other: the engine returns trades and bars, the
analytics layer consumes plain records. This service translates, which is why
the same report can be produced from a run that just finished *or* from the JSON
snapshot of a run saved months ago - the path Run Comparison, Monte Carlo and
PDF export will all take.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from typing import Any

from app.analytics import AnalyticsConfig, AnalyticsInput, AnalyticsReport, BarRecord, TradeRecord
from app.analytics.metrics import PerformanceAnalytics
from app.domain.enums import PositionSide
from app.engine.execution.trade import Trade
from app.engine.results.chart_data import Candle
from app.engine.results.result import ExecutionResult


class AnalyticsService:
    """Produces a performance and risk report for one run."""

    def __init__(self, analytics: PerformanceAnalytics | None = None) -> None:
        self.analytics = analytics or PerformanceAnalytics()

    def analyse_result(
        self,
        result: ExecutionResult,
        *,
        initial_capital: float,
        config: AnalyticsConfig | None = None,
    ) -> AnalyticsReport:
        """Report for a replay that just finished.

        ``result.candles`` must already be populated - it is the bar series every
        risk metric marks positions against. A result without candles still
        produces a report; the metrics that need prices degrade to ``None``.
        """
        return self.analytics.analyse(
            AnalyticsInput(
                trades=tuple(_trade_record(trade) for trade in result.trades),
                bars=tuple(_bar_record(candle) for candle in result.candles),
                initial_capital=initial_capital,
                config=config or AnalyticsConfig(),
            )
        )

    def analyse_snapshot(
        self,
        *,
        trades: Sequence[Mapping[str, Any]],
        candles: Sequence[Mapping[str, Any]],
        initial_capital: float,
        config: AnalyticsConfig | None = None,
    ) -> AnalyticsReport:
        """Report rebuilt from a persisted run's JSON snapshots.

        Used to backfill runs recorded before analytics existed, so an old result
        page is never blank. The snapshot is immutable, so the report is
        identical to what the run would produce today under the same analytics
        version.
        """
        return self.analytics.analyse(
            AnalyticsInput(
                trades=tuple(_trade_record_from_json(row) for row in trades),
                bars=tuple(_bar_record_from_json(row) for row in candles),
                initial_capital=initial_capital,
                config=config or AnalyticsConfig(),
            )
        )

    @staticmethod
    def to_json(report: AnalyticsReport) -> str:
        """Serialise a report for the ``backtest_runs.analytics_json`` column."""
        payload = asdict(report)
        payload["metrics"] = [asdict(value) for value in report.metric_values()]
        return json.dumps(payload, separators=(",", ":"), sort_keys=True, default=str)


def _trade_record(trade: Trade) -> TradeRecord:
    return TradeRecord(
        seq=trade.seq,
        side=trade.side,
        quantity=trade.quantity,
        entry_ts=trade.entry_ts,
        entry_price=trade.entry_price,
        exit_ts=trade.exit_ts,
        exit_price=trade.exit_price,
        gross_pnl=trade.gross_pnl,
        commission=trade.commission,
        slippage_cost=trade.slippage_cost,
        net_pnl=trade.net_pnl,
        bars_held=trade.bars_held,
    )


def _bar_record(candle: Candle) -> BarRecord:
    return BarRecord(
        ts=candle.ts,
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
    )


def _trade_record_from_json(row: Mapping[str, Any]) -> TradeRecord:
    return TradeRecord(
        seq=int(row["seq"]),
        side=PositionSide(row["side"]),
        quantity=float(row["quantity"]),
        entry_ts=int(row["entry_ts"]),
        entry_price=float(row["entry_price"]),
        exit_ts=int(row["exit_ts"]),
        exit_price=float(row["exit_price"]),
        gross_pnl=float(row["gross_pnl"]),
        commission=float(row["commission"]),
        slippage_cost=float(row["slippage_cost"]),
        net_pnl=float(row["net_pnl"]),
        bars_held=int(row["bars_held"]),
    )


def _bar_record_from_json(row: Mapping[str, Any]) -> BarRecord:
    return BarRecord(
        ts=int(row["ts"]),
        open=float(row["open"]),
        high=float(row["high"]),
        low=float(row["low"]),
        close=float(row["close"]),
        volume=float(row.get("volume", 0.0)),
    )
