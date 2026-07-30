"""Deserialize a persisted analytics JSON snapshot back into dataclasses."""

from __future__ import annotations

import json
from typing import Any

from app.analytics.monthly import MonthlyReturn
from app.analytics.portfolio import (
    DailyPnlPoint,
    DrawdownPoint,
    EquityPoint,
    PortfolioMetrics,
    PortfolioSeries,
    RollingReturnPoint,
)
from app.analytics.report import AnalyticsMeta, AnalyticsReport
from app.analytics.returns import ReturnMetrics
from app.analytics.risk import RiskMetrics
from app.analytics.risk_adjusted import RiskAdjustedMetrics
from app.analytics.statistics import StatisticalMetrics
from app.analytics.trades import TradeMetrics
from app.analytics.yearly import YearlyReturn


def report_from_json(text: str) -> AnalyticsReport:
    """Rebuild an ``AnalyticsReport`` from ``AnalyticsService.to_json`` output."""
    return report_from_dict(json.loads(text))


def report_from_dict(data: dict[str, Any]) -> AnalyticsReport:
    series = data["series"]
    return AnalyticsReport(
        returns=ReturnMetrics(**data["returns"]),
        risk=RiskMetrics(**data["risk"]),
        risk_adjusted=RiskAdjustedMetrics(**data["risk_adjusted"]),
        trades=TradeMetrics(**data["trades"]),
        portfolio=PortfolioMetrics(**data["portfolio"]),
        statistics=StatisticalMetrics(**data["statistics"]),
        series=PortfolioSeries(
            equity_curve=tuple(EquityPoint(**point) for point in series["equity_curve"]),
            drawdown_curve=tuple(DrawdownPoint(**point) for point in series["drawdown_curve"]),
            daily_pnl=tuple(DailyPnlPoint(**point) for point in series["daily_pnl"]),
            rolling_returns=tuple(
                RollingReturnPoint(**point) for point in series["rolling_returns"]
            ),
            monthly_returns=tuple(MonthlyReturn(**point) for point in series["monthly_returns"]),
            yearly_returns=tuple(YearlyReturn(**point) for point in series["yearly_returns"]),
            max_drawdown_start_ts=series.get("max_drawdown_start_ts"),
            max_drawdown_trough_ts=series.get("max_drawdown_trough_ts"),
            max_drawdown_recovery_ts=series.get("max_drawdown_recovery_ts"),
            curves_downsampled=bool(series.get("curves_downsampled", False)),
        ),
        meta=AnalyticsMeta(**data["meta"]),
    )
