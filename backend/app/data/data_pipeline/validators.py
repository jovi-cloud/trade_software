"""Schema, OHLC, and data-quality validation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import polars as pl

from app.data.data_pipeline.metadata import MAX_SAMPLE_COUNT
from app.data.data_pipeline.report import ValidationReport
from app.data.schema import NUMERIC_COLUMNS
from app.domain.enums import Timeframe


def _epoch_ms_to_iso(epoch_ms: int) -> str:
    return datetime.fromtimestamp(epoch_ms / 1000, tz=UTC).isoformat()


def _empty_bars() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "ts": pl.Int64,
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
        }
    )


def _parse_timestamps(column: pl.Series) -> pl.Series:
    try:
        return column.str.strip_chars().str.to_datetime(strict=False, time_unit="ms")
    except pl.exceptions.ComputeError:
        return pl.Series([None] * len(column), dtype=pl.Datetime(time_unit="ms"))


def validate_and_normalise(
    raw: pl.DataFrame,
    *,
    timeframe: Timeframe | None = None,
    remove_duplicate_timestamps: bool = True,
) -> tuple[pl.DataFrame, ValidationReport]:
    """Parse, validate, and normalise raw string bars to canonical typed form."""
    total_rows = raw.height
    if total_rows == 0:
        return _empty_bars(), ValidationReport(
            total_rows=0,
            valid_rows=0,
            invalid_dates=0,
            invalid_prices=0,
            duplicate_timestamps=0,
            missing_timestamps=0,
        )

    parsed = raw.with_columns(
        _parse_timestamps(raw["timestamp"]).alias("_ts"),
        *[
            pl.col(c).str.strip_chars().cast(pl.Float64, strict=False).alias(f"_{c}")
            for c in NUMERIC_COLUMNS
        ],
    )

    invalid_dates = int(parsed.select(pl.col("_ts").is_null().sum()).item())

    nan_mask = pl.any_horizontal([pl.col(f"_{c}").is_nan() for c in NUMERIC_COLUMNS])
    inf_mask = pl.any_horizontal([pl.col(f"_{c}").is_infinite() for c in NUMERIC_COLUMNS])
    nan_values = int(parsed.filter(nan_mask).height)
    infinity_values = int(parsed.filter(inf_mask).height)

    invalid_price_mask = pl.any_horizontal(
        [pl.col(f"_{c}").is_null() for c in NUMERIC_COLUMNS]
    ) | nan_mask | inf_mask
    invalid_prices = int(parsed.filter(invalid_price_mask).height)

    clean = parsed.filter(pl.col("_ts").is_not_null() & ~invalid_price_mask)

    out_of_order_timestamps = 0
    if clean.height > 1:
        original_order = clean.select("_ts").to_series().to_list()
        sorted_order = sorted(original_order)
        out_of_order_timestamps = sum(
            1 for left, right in zip(original_order, sorted_order, strict=True) if left != right
        )
        clean = clean.sort("_ts")

    duplicate_timestamps = 0
    duplicate_samples: tuple[str, ...] = ()
    if remove_duplicate_timestamps:
        before = clean.height
        deduped = clean.unique(subset=["_ts"], keep="first").sort("_ts")
        duplicate_timestamps = before - deduped.height
        if duplicate_timestamps > 0:
            dup_ts = (
                clean.filter(pl.col("_ts").is_duplicated())
                .select(pl.col("_ts").dt.epoch(time_unit="ms"))
                .to_series()
                .unique()
                .sort()
                .head(MAX_SAMPLE_COUNT)
                .to_list()
            )
            duplicate_samples = tuple(_epoch_ms_to_iso(ts) for ts in dup_ts)
        clean = deduped
    else:
        deduped = clean

    valid_rows = deduped.height
    if valid_rows == 0:
        return _empty_bars(), ValidationReport(
            total_rows=total_rows,
            valid_rows=0,
            invalid_dates=invalid_dates,
            invalid_prices=invalid_prices,
            duplicate_timestamps=duplicate_timestamps,
            missing_timestamps=0,
            out_of_order_timestamps=out_of_order_timestamps,
            nan_values=nan_values,
            infinity_values=infinity_values,
            duplicate_samples=duplicate_samples,
        )

    bars = deduped.select(
        pl.col("_ts").dt.epoch(time_unit="ms").alias("ts"),
        pl.col("_open").alias("open"),
        pl.col("_high").alias("high"),
        pl.col("_low").alias("low"),
        pl.col("_close").alias("close"),
        pl.col("_volume").alias("volume"),
    )

    ohlc_mask = (
        (pl.col("high") < pl.col("low"))
        | (pl.col("open") > pl.col("high"))
        | (pl.col("open") < pl.col("low"))
        | (pl.col("close") > pl.col("high"))
        | (pl.col("close") < pl.col("low"))
    )
    negative_volume_mask = pl.col("volume") < 0
    non_positive_price_mask = (
        (pl.col("open") <= 0)
        | (pl.col("high") <= 0)
        | (pl.col("low") <= 0)
        | (pl.col("close") <= 0)
    )

    ohlc_violations = int(bars.filter(ohlc_mask).height)
    negative_volumes = int(bars.filter(negative_volume_mask).height)
    non_positive_prices = int(bars.filter(non_positive_price_mask).height)

    bars = bars.filter(~ohlc_mask & ~negative_volume_mask & ~non_positive_price_mask)
    valid_rows = bars.height

    ts_ms = bars.select("ts").to_series() if valid_rows else pl.Series([], dtype=pl.Int64)
    start_date = end_date = None
    missing_timestamps = 0
    gap_samples: tuple[str, ...] = ()

    if valid_rows > 0:
        min_ts = cast(int, ts_ms.min())
        max_ts = cast(int, ts_ms.max())
        start_date = datetime.fromtimestamp(min_ts / 1000, tz=UTC)
        end_date = datetime.fromtimestamp(max_ts / 1000, tz=UTC)

    report = ValidationReport(
        total_rows=total_rows,
        valid_rows=valid_rows,
        invalid_dates=invalid_dates,
        invalid_prices=invalid_prices,
        duplicate_timestamps=duplicate_timestamps,
        missing_timestamps=missing_timestamps,
        out_of_order_timestamps=out_of_order_timestamps,
        ohlc_violations=ohlc_violations,
        negative_volumes=negative_volumes,
        non_positive_prices=non_positive_prices,
        nan_values=nan_values,
        infinity_values=infinity_values,
        start_date=start_date,
        end_date=end_date,
        duplicate_samples=duplicate_samples,
        gap_samples=gap_samples,
    )
    return bars, report
