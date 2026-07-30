"""Parquet output for validated bar data."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from app.data import store


def write_bars(df: pl.DataFrame, path: Path) -> None:
    """Write canonical bars to Parquet using the shared bar store."""
    store.write_parquet(df, path)
