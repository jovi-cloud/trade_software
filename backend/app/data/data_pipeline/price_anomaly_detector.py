"""Detect abnormal price moves within a day and across consecutive trading days."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import polars as pl

from app.data.data_pipeline.metadata import MAX_SAMPLE_COUNT, SessionConfig
from app.data.data_pipeline.report import PriceAnomalyReport

MODERATE_SPIKE_PCT = 10.0
SEVERE_SPIKE_PCT = 20.0


def _epoch_ms_to_local_iso(epoch_ms: int, tz: ZoneInfo) -> str:
    return datetime.fromtimestamp(epoch_ms / 1000, tz=UTC).astimezone(tz).isoformat()


def _format_intraday_spike_sample(
    ts: int,
    *,
    prev_close: float,
    close: float,
    pct_change: float,
    tz: ZoneInfo,
) -> str:
    when = _epoch_ms_to_local_iso(ts, tz)
    direction = "+" if close >= prev_close else "-"
    return (
        f"{when}: {direction}{pct_change:.2f}% "
        f"({prev_close:.4g} → {close:.4g})"
    )


def _format_cross_day_spike_sample(
    prev_day: str,
    curr_day: str,
    *,
    prev_close: float,
    curr_open: float,
    pct_change: float,
) -> str:
    direction = "+" if curr_open >= prev_close else "-"
    return (
        f"{prev_day} → {curr_day}: {direction}{pct_change:.2f}% "
        f"({prev_close:.4g} close → {curr_open:.4g} open)"
    )


def _count_bars_on_days(bars: pl.DataFrame, day_keys: list[str], local: pl.Expr) -> int:
    if not day_keys:
        return 0
    annotated = bars.with_columns(local.dt.strftime("%Y-%m-%d").alias("_day_key"))
    return int(annotated.filter(pl.col("_day_key").is_in(day_keys)).height)


def _collect_intraday_spikes(
    bars: pl.DataFrame,
    *,
    local: pl.Expr,
    tz: ZoneInfo,
    moderate_threshold_pct: float,
    severe_threshold_pct: float,
) -> tuple[int, int, list[str], list[str], list[str], list[str]]:
    annotated = (
        bars.sort("ts")
        .with_columns(
            local.alias("_local"),
            local.dt.strftime("%Y-%m-%d").alias("_day_key"),
            pl.col("close").shift(1).alias("_prev_close"),
        )
        .with_columns(
            pl.col("_day_key").shift(1).alias("_prev_day"),
        )
        .with_columns(
            (
                (pl.col("close") - pl.col("_prev_close")).abs()
                / pl.col("_prev_close")
                * 100.0
            ).alias("_pct_change")
        )
        .filter(
            pl.col("_prev_close").is_not_null()
            & (pl.col("_prev_close") > 0)
            & (pl.col("_day_key") == pl.col("_prev_day"))
        )
    )

    moderate_mask = pl.col("_pct_change") > moderate_threshold_pct
    severe_mask = pl.col("_pct_change") > severe_threshold_pct

    spikes_over_10 = int(annotated.filter(moderate_mask).height)
    spikes_over_20 = int(annotated.filter(severe_mask).height)

    days_over_10 = sorted(
        annotated.filter(moderate_mask).select("_day_key").unique().to_series().to_list()
    )
    days_over_20 = sorted(
        annotated.filter(severe_mask).select("_day_key").unique().to_series().to_list()
    )

    samples_10: list[str] = []
    samples_20: list[str] = []
    for row in annotated.filter(moderate_mask).iter_rows(named=True):
        if len(samples_10) >= MAX_SAMPLE_COUNT:
            break
        samples_10.append(
            _format_intraday_spike_sample(
                int(row["ts"]),
                prev_close=float(row["_prev_close"]),
                close=float(row["close"]),
                pct_change=float(row["_pct_change"]),
                tz=tz,
            )
        )
    for row in annotated.filter(severe_mask).iter_rows(named=True):
        if len(samples_20) >= MAX_SAMPLE_COUNT:
            break
        samples_20.append(
            _format_intraday_spike_sample(
                int(row["ts"]),
                prev_close=float(row["_prev_close"]),
                close=float(row["close"]),
                pct_change=float(row["_pct_change"]),
                tz=tz,
            )
        )

    return spikes_over_10, spikes_over_20, days_over_10, days_over_20, samples_10, samples_20


def _collect_cross_day_spikes(
    bars: pl.DataFrame,
    *,
    local: pl.Expr,
    moderate_threshold_pct: float,
    severe_threshold_pct: float,
) -> tuple[int, int, list[str], list[str], list[str], list[str]]:
    daily = (
        bars.sort("ts")
        .with_columns(
            local.dt.strftime("%Y-%m-%d").alias("_day_key"),
        )
        .group_by("_day_key")
        .agg(
            pl.col("ts").first().alias("_first_ts"),
            pl.col("open").first().alias("_first_open"),
            pl.col("close").last().alias("_last_close"),
        )
        .sort("_first_ts")
        .with_columns(
            pl.col("_last_close").shift(1).alias("_prev_close"),
            pl.col("_day_key").shift(1).alias("_prev_day"),
        )
        .filter(pl.col("_prev_close").is_not_null() & (pl.col("_prev_close") > 0))
        .with_columns(
            (
                (pl.col("_first_open") - pl.col("_prev_close")).abs()
                / pl.col("_prev_close")
                * 100.0
            ).alias("_pct_change")
        )
    )

    moderate_mask = pl.col("_pct_change") > moderate_threshold_pct
    severe_mask = pl.col("_pct_change") > severe_threshold_pct

    spikes_over_10 = int(daily.filter(moderate_mask).height)
    spikes_over_20 = int(daily.filter(severe_mask).height)

    def _days_for_mask(mask: pl.Expr) -> list[str]:
        flagged = daily.filter(mask)
        days: set[str] = set()
        for prev_day, curr_day in zip(
            flagged["_prev_day"].to_list(),
            flagged["_day_key"].to_list(),
            strict=False,
        ):
            days.add(str(prev_day))
            days.add(str(curr_day))
        return sorted(days)

    days_over_10 = _days_for_mask(moderate_mask)
    days_over_20 = _days_for_mask(severe_mask)

    samples_10: list[str] = []
    samples_20: list[str] = []
    for row in daily.filter(moderate_mask).iter_rows(named=True):
        if len(samples_10) >= MAX_SAMPLE_COUNT:
            break
        samples_10.append(
            _format_cross_day_spike_sample(
                str(row["_prev_day"]),
                str(row["_day_key"]),
                prev_close=float(row["_prev_close"]),
                curr_open=float(row["_first_open"]),
                pct_change=float(row["_pct_change"]),
            )
        )
    for row in daily.filter(severe_mask).iter_rows(named=True):
        if len(samples_20) >= MAX_SAMPLE_COUNT:
            break
        samples_20.append(
            _format_cross_day_spike_sample(
                str(row["_prev_day"]),
                str(row["_day_key"]),
                prev_close=float(row["_prev_close"]),
                curr_open=float(row["_first_open"]),
                pct_change=float(row["_pct_change"]),
            )
        )

    return spikes_over_10, spikes_over_20, days_over_10, days_over_20, samples_10, samples_20


def detect_price_anomalies(
    bars: pl.DataFrame,
    *,
    session: SessionConfig | None = None,
    moderate_threshold_pct: float = MODERATE_SPIKE_PCT,
    severe_threshold_pct: float = SEVERE_SPIKE_PCT,
) -> PriceAnomalyReport:
    """Flag abnormal close moves within a day and across consecutive trading days."""
    session_config = session or SessionConfig()
    if bars.height < 2:
        return PriceAnomalyReport()

    tz = ZoneInfo(session_config.timezone)
    local = (
        pl.from_epoch(pl.col("ts"), time_unit="ms")
        .dt.replace_time_zone("UTC")
        .dt.convert_time_zone(session_config.timezone)
    )

    (
        intraday_10,
        intraday_20,
        intraday_days_10,
        intraday_days_20,
        intraday_samples_10,
        intraday_samples_20,
    ) = _collect_intraday_spikes(
        bars,
        local=local,
        tz=tz,
        moderate_threshold_pct=moderate_threshold_pct,
        severe_threshold_pct=severe_threshold_pct,
    )

    (
        cross_day_10,
        cross_day_20,
        cross_day_days_10,
        cross_day_days_20,
        cross_day_samples_10,
        cross_day_samples_20,
    ) = _collect_cross_day_spikes(
        bars,
        local=local,
        moderate_threshold_pct=moderate_threshold_pct,
        severe_threshold_pct=severe_threshold_pct,
    )

    union_days_10 = sorted(set(intraday_days_10) | set(cross_day_days_10))
    union_days_20 = sorted(set(intraday_days_20) | set(cross_day_days_20))

    return PriceAnomalyReport(
        spikes_over_10_pct=intraday_10,
        spikes_over_20_pct=intraday_20,
        cross_day_spikes_over_10_pct=cross_day_10,
        cross_day_spikes_over_20_pct=cross_day_20,
        intraday_days_over_10_samples=tuple(intraday_days_10),
        intraday_days_over_20_samples=tuple(intraday_days_20),
        intraday_bars_on_days_over_10_pct=_count_bars_on_days(bars, intraday_days_10, local),
        intraday_bars_on_days_over_20_pct=_count_bars_on_days(bars, intraday_days_20, local),
        cross_day_days_over_10_samples=tuple(cross_day_days_10),
        cross_day_days_over_20_samples=tuple(cross_day_days_20),
        cross_day_bars_on_days_over_10_pct=_count_bars_on_days(bars, cross_day_days_10, local),
        cross_day_bars_on_days_over_20_pct=_count_bars_on_days(bars, cross_day_days_20, local),
        days_with_spikes_over_10_pct=len(union_days_10),
        days_with_spikes_over_20_pct=len(union_days_20),
        bars_on_days_over_10_pct=_count_bars_on_days(bars, union_days_10, local),
        bars_on_days_over_20_pct=_count_bars_on_days(bars, union_days_20, local),
        spike_over_10_samples=tuple(intraday_samples_10),
        spike_over_20_samples=tuple(intraday_samples_20),
        cross_day_spike_over_10_samples=tuple(cross_day_samples_10),
        cross_day_spike_over_20_samples=tuple(cross_day_samples_20),
        days_over_10_samples=tuple(union_days_10),
        days_over_20_samples=tuple(union_days_20),
    )
