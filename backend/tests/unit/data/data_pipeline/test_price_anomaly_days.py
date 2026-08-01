"""Tests for resolving no-trade days from pipeline reports."""

from __future__ import annotations

import json

from app.data.data_pipeline.price_anomaly_days import (
    PriceAnomalyTradeSkipOptions,
    resolve_no_trade_days,
)


def test_resolve_no_trade_days_unions_selected_anomaly_classes() -> None:
    report = {
        "price_anomalies": {
            "intraday_days_over_10_samples": ["2024-01-01"],
            "intraday_days_over_20_samples": ["2024-01-02"],
            "cross_day_days_over_10_samples": ["2024-01-03", "2024-01-04"],
            "cross_day_days_over_20_samples": ["2024-01-05"],
        }
    }

    days = resolve_no_trade_days(
        json.dumps(report),
        options=PriceAnomalyTradeSkipOptions(
            intraday_over_10pct=True,
            intraday_over_20pct=False,
            cross_day_over_10pct=True,
            cross_day_over_20pct=False,
        ),
    )

    assert days == frozenset({"2024-01-01", "2024-01-03", "2024-01-04"})
