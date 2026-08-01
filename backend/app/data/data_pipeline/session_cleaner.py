"""Remove session-boundary violations from normalised bar data."""

from __future__ import annotations

import polars as pl

from app.data.data_pipeline.metadata import SessionCleaningOptions, SessionConfig
from app.data.data_pipeline.report import CleaningAction, CleaningReport
from app.data.data_pipeline.session_bounds import resolve_session_bar_bounds


def clean_session_bars(
    bars: pl.DataFrame,
    config: SessionConfig,
    options: SessionCleaningOptions,
) -> tuple[pl.DataFrame, CleaningReport]:
    """Drop bars that violate exchange session rules.

    Missing opening/closing candles are gaps (absence of data), not removable rows.
    """
    if bars.height == 0 or not options.enabled:
        return bars, CleaningReport()

    bounds = resolve_session_bar_bounds(config.open_time, config.close_time)
    trading_days = set(config.trading_days)
    holidays = config.holidays

    local = (
        pl.from_epoch(pl.col("ts"), time_unit="ms")
        .dt.replace_time_zone("UTC")
        .dt.convert_time_zone(config.timezone)
    )
    annotated = bars.with_columns(
        local.alias("_local"),
        (local.dt.hour().cast(pl.Int32) * 60 + local.dt.minute().cast(pl.Int32)).alias("_minutes"),
        (local.dt.weekday() - 1).alias("_weekday"),
        local.dt.strftime("%Y-%m-%d").alias("_day_key"),
    )

    remove_mask = pl.lit(False)
    actions: list[CleaningAction] = []

    if options.remove_weekend_bars:
        weekend_mask = ~pl.col("_weekday").is_in(list(trading_days))
        removed = int(annotated.filter(weekend_mask).height)
        if removed:
            actions.append(CleaningAction("remove_weekend_bars", removed))
        remove_mask = remove_mask | weekend_mask

    if options.remove_holiday_bars and holidays:
        holiday_mask = pl.col("_day_key").is_in(list(holidays))
        removed = int(annotated.filter(holiday_mask).height)
        if removed:
            actions.append(CleaningAction("remove_holiday_bars", removed))
        remove_mask = remove_mask | holiday_mask

    if options.remove_outside_session:
        outside_mask = (pl.col("_minutes") < bounds.open_minutes) | (
            pl.col("_minutes") > bounds.last_bar_minutes
        )
        removed = int(annotated.filter(outside_mask).height)
        if removed:
            actions.append(
                CleaningAction(
                    "remove_outside_session_bars",
                    removed,
                    f"{config.open_time}–{config.close_time} {config.timezone}",
                )
            )
        remove_mask = remove_mask | outside_mask

    filtered = annotated.with_columns(remove_mask.alias("_remove")).filter(~pl.col("_remove"))
    return filtered.select(bars.columns), CleaningReport(actions=tuple(actions))
