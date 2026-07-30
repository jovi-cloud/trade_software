"""Strict bar validation before engine execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import polars as pl

from app.data.errors import InvalidBarsError
from app.data.schema import CANONICAL_COLUMNS


@dataclass(frozen=True)
class BarsValidationSummary:
    row_count: int
    duplicate_timestamps: int
    out_of_order_timestamps: int
    ohlc_violations: int
    negative_volumes: int
    non_positive_prices: int
    missing_values: int


def _as_frame(rows: list[dict[str, Any]]) -> pl.DataFrame:
    if not rows:
        return pl.DataFrame(schema={column: pl.Float64 for column in CANONICAL_COLUMNS})
    return pl.DataFrame(rows)


def validate_bars_strict(rows: list[dict[str, Any]]) -> BarsValidationSummary:
    """Validate canonical bars given as row mappings.

    Kept for callers that already hold rows. The run path validates the frame
    directly - see :func:`validate_bar_frame` - because converting a few million
    bars into dicts just to check them is what this module exists to avoid.
    """
    return validate_bar_frame(_as_frame(rows))


def validate_bar_frame(frame: pl.DataFrame) -> BarsValidationSummary:
    """Validate canonical bars and raise ``InvalidBarsError`` when unusable.

    Every check is a columnar aggregate, so cost scales with the *width* of the
    work rather than with Python object count: a 2 M-bar dataset is validated
    without ever holding 2 M row objects.
    """
    if frame.height == 0:
        raise InvalidBarsError("Dataset contains no bars")

    missing_values = int(
        frame.select(pl.any_horizontal([pl.col(column).is_null() for column in CANONICAL_COLUMNS])).sum().item()
    )
    duplicate_timestamps = frame.height - frame.select("ts").unique().height
    out_of_order = int((frame["ts"].diff().drop_nulls() < 0).sum())
    non_positive_prices = int(
        frame.select(
            pl.any_horizontal(
                [
                    (pl.col("open") <= 0)
                    | (pl.col("high") <= 0)
                    | (pl.col("low") <= 0)
                    | (pl.col("close") <= 0)
                ]
            ).sum()
        ).item()
    )
    negative_volumes = int((frame["volume"] < 0).sum())
    ohlc_violations = int(
        frame.select(
            (
                (pl.col("high") < pl.col("low"))
                | (pl.col("open") > pl.col("high"))
                | (pl.col("open") < pl.col("low"))
                | (pl.col("close") > pl.col("high"))
                | (pl.col("close") < pl.col("low"))
            ).sum()
        ).item()
    )

    summary = BarsValidationSummary(
        row_count=frame.height,
        duplicate_timestamps=duplicate_timestamps,
        out_of_order_timestamps=out_of_order,
        ohlc_violations=ohlc_violations,
        negative_volumes=negative_volumes,
        non_positive_prices=non_positive_prices,
        missing_values=missing_values,
    )

    problems: list[str] = []
    if missing_values:
        problems.append(f"{missing_values} row(s) contain missing values")
    if duplicate_timestamps:
        problems.append(f"{duplicate_timestamps} duplicate timestamp(s)")
    if out_of_order:
        problems.append(f"{out_of_order} out-of-order timestamp transition(s)")
    if ohlc_violations:
        problems.append(f"{ohlc_violations} OHLC consistency violation(s)")
    if negative_volumes:
        problems.append(f"{negative_volumes} negative volume row(s)")
    if non_positive_prices:
        problems.append(f"{non_positive_prices} non-positive price row(s)")

    if problems:
        raise InvalidBarsError("; ".join(problems), summary=summary)
    return summary
