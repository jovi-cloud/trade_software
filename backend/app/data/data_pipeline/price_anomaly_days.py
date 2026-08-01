"""Resolve trading-day exclusions from a stored pipeline report."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class PriceAnomalyTradeSkipOptions:
    intraday_over_10pct: bool = True
    intraday_over_20pct: bool = True
    cross_day_over_10pct: bool = True
    cross_day_over_20pct: bool = True


def resolve_no_trade_days(
    report_json: str | None,
    *,
    options: PriceAnomalyTradeSkipOptions,
) -> frozenset[str]:
    """Union of session dates to skip new entries on, from a pipeline report."""
    if not report_json:
        return frozenset()

    try:
        parsed = json.loads(report_json)
    except json.JSONDecodeError:
        return frozenset()

    anomalies = parsed.get("price_anomalies")
    if not isinstance(anomalies, dict):
        return frozenset()

    days: set[str] = set()
    if options.intraday_over_10pct:
        days.update(_as_day_list(anomalies.get("intraday_days_over_10_samples")))
    if options.intraday_over_20pct:
        days.update(_as_day_list(anomalies.get("intraday_days_over_20_samples")))
    if options.cross_day_over_10pct:
        days.update(_as_day_list(anomalies.get("cross_day_days_over_10_samples")))
    if options.cross_day_over_20pct:
        days.update(_as_day_list(anomalies.get("cross_day_days_over_20_samples")))

    return frozenset(days)


def _as_day_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]
