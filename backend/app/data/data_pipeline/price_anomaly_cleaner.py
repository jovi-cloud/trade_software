"""Remove trading days flagged for abnormal price moves."""

from __future__ import annotations

import polars as pl

from app.data.data_pipeline.metadata import SessionCleaningOptions, SessionConfig
from app.data.data_pipeline.report import CleaningAction, CleaningReport, PriceAnomalyReport


def clean_price_anomaly_days(
    bars: pl.DataFrame,
    anomaly_report: PriceAnomalyReport,
    config: SessionConfig,
    options: SessionCleaningOptions,
) -> tuple[pl.DataFrame, CleaningReport]:
    """Drop all bars on days flagged by intraday or cross-day price spike rules."""
    if bars.height == 0 or not options.price_anomaly_cleaning_enabled:
        return bars, CleaningReport()

    days_to_remove: set[str] = set()
    if options.remove_days_with_spikes_over_10pct:
        days_to_remove.update(anomaly_report.days_over_10_samples)
    if options.remove_days_with_spikes_over_20pct:
        days_to_remove.update(anomaly_report.days_over_20_samples)
    if options.remove_intraday_spike_days_over_10pct:
        days_to_remove.update(anomaly_report.intraday_days_over_10_samples)
    if options.remove_intraday_spike_days_over_20pct:
        days_to_remove.update(anomaly_report.intraday_days_over_20_samples)
    if options.remove_cross_day_spike_days_over_10pct:
        days_to_remove.update(anomaly_report.cross_day_days_over_10_samples)
    if options.remove_cross_day_spike_days_over_20pct:
        days_to_remove.update(anomaly_report.cross_day_days_over_20_samples)

    if not days_to_remove:
        return bars, CleaningReport()

    local = (
        pl.from_epoch(pl.col("ts"), time_unit="ms")
        .dt.replace_time_zone("UTC")
        .dt.convert_time_zone(config.timezone)
    )
    annotated = bars.with_columns(
        local.dt.strftime("%Y-%m-%d").alias("_day_key"),
    )
    remove_mask = pl.col("_day_key").is_in(list(days_to_remove))
    removed = int(annotated.filter(remove_mask).height)
    if removed == 0:
        return bars, CleaningReport()

    filtered = annotated.filter(~remove_mask).select(bars.columns)
    return filtered, CleaningReport(
        actions=(
            CleaningAction(
                "remove_price_anomaly_days",
                removed,
                f"{len(days_to_remove)} trading day(s)",
            ),
        )
    )
