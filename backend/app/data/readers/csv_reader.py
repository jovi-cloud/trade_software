"""CSV -> raw Polars DataFrame. No parsing or validation - see app.data.validator."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from app.data.errors import MissingColumnsError
from app.data.schema import REQUIRED_COLUMNS


def read_csv(path: Path) -> pl.DataFrame:
    """Read every column as a string.

    ``app.data.validator`` controls all parsing and casting, so a malformed
    value is something it counts as invalid rather than something Polars'
    type inference silently turns into a null before validation ever sees it.
    """
    df = pl.read_csv(path, infer_schema_length=0)
    df = df.rename({c: c.strip().lower() for c in df.columns})

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise MissingColumnsError(missing)

    return df.select(list(REQUIRED_COLUMNS))
