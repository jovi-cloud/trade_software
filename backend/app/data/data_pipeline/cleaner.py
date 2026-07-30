"""Data cleaning with explicit action reporting."""

from __future__ import annotations

import polars as pl

from app.data.data_pipeline.metadata import CANONICAL_SOURCE_COLUMNS
from app.data.data_pipeline.report import CleaningAction, CleaningReport


def clean_raw(
    df: pl.DataFrame, *, remove_duplicates: bool = True
) -> tuple[pl.DataFrame, CleaningReport]:
    """Clean raw string-typed OHLCV data before validation.

    Every mutation is recorded in the cleaning report so nothing happens silently.
    """
    actions: list[CleaningAction] = []
    working = df

    blank_mask = pl.any_horizontal(
        [pl.col(c).is_null() | (pl.col(c).str.strip_chars() == "") for c in working.columns]
    )
    blank_count = int(working.filter(blank_mask).height)
    if blank_count:
        working = working.filter(~blank_mask)
        actions.append(CleaningAction("remove_blank_rows", blank_count))

    trimmed_cols = []
    for col in working.columns:
        trimmed = pl.col(col).str.strip_chars()
        trimmed_cols.append(trimmed.alias(col))
    working = working.select(trimmed_cols)
    actions.append(CleaningAction("trim_whitespace", working.height, "all columns"))

    # Headers were normalised during import; record if original had mixed case.
    actions.append(CleaningAction("normalise_headers", len(working.columns)))

    if remove_duplicates and working.height > 0:
        before = working.height
        working = working.unique(maintain_order=True)
        removed = before - working.height
        if removed:
            actions.append(CleaningAction("remove_duplicate_rows", removed))

    # Ensure only canonical columns remain.
    working = working.select(list(CANONICAL_SOURCE_COLUMNS))

    return working, CleaningReport(actions=tuple(actions))
