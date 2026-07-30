"""Format detection and raw file reading for the data pipeline."""

from __future__ import annotations

import io
from enum import StrEnum
from pathlib import Path

import polars as pl

from app.data.data_pipeline.metadata import (
    ALIAS_GROUPS,
    CANONICAL_SOURCE_COLUMNS,
)
from app.data.errors import MissingColumnsError


class InputFormat(StrEnum):
    CSV = "csv"
    XLSX = "xlsx"
    PARQUET = "parquet"


def detect_format(path: Path, *, content: bytes | None = None) -> InputFormat:
    """Detect file format from extension, falling back to magic bytes."""
    suffix = path.suffix.lower()
    if suffix in {".csv", ".txt"}:
        return InputFormat.CSV
    if suffix in {".xlsx", ".xls"}:
        return InputFormat.XLSX
    if suffix in {".parquet", ".pq"}:
        return InputFormat.PARQUET

    if content is not None:
        if content[:4] == b"PAR1":
            return InputFormat.PARQUET
        if content[:2] == b"PK":
            return InputFormat.XLSX
    return InputFormat.CSV


def _normalise_header(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def _build_column_rename(
    columns: list[str],
    explicit_mapping: dict[str, str] | None = None,
) -> dict[str, str]:
    """Map raw headers to canonical source column names."""
    explicit_mapping = explicit_mapping or {}
    normalised = {_normalise_header(col): col for col in columns}
    rename: dict[str, str] = {}

    for canonical, aliases in ALIAS_GROUPS.items():
        if canonical in explicit_mapping:
            source_key = _normalise_header(explicit_mapping[canonical])
            if source_key in normalised:
                rename[normalised[source_key]] = canonical
            continue
        for alias in aliases:
            if alias in normalised:
                rename[normalised[alias]] = canonical
                break

    return rename


def _apply_column_mapping(df: pl.DataFrame, mapping: dict[str, str]) -> pl.DataFrame:
    rename = _build_column_rename(list(df.columns), mapping)
    if not rename:
        missing = [c for c in CANONICAL_SOURCE_COLUMNS if c not in df.columns]
        if missing:
            raise MissingColumnsError(missing)
        return df.select(list(CANONICAL_SOURCE_COLUMNS))

    df = df.rename(rename)
    missing = [c for c in CANONICAL_SOURCE_COLUMNS if c not in df.columns]
    if missing:
        raise MissingColumnsError(missing)
    return df.select(list(CANONICAL_SOURCE_COLUMNS))


def read_raw(
    path: Path,
    *,
    column_mapping: dict[str, str] | None = None,
    fmt: InputFormat | None = None,
) -> pl.DataFrame:
    """Read a file into a string-typed DataFrame with canonical source columns."""
    detected = fmt or detect_format(path)
    if detected == InputFormat.CSV:
        df = pl.read_csv(path, infer_schema_length=0)
    elif detected == InputFormat.XLSX:
        df = pl.read_excel(path, infer_schema_length=0)
    else:
        df = pl.read_parquet(path)
        if df.schema.get("ts") is not None and "timestamp" not in df.columns:
            df = df.rename({"ts": "timestamp"})
        for col in df.columns:
            df = df.with_columns(pl.col(col).cast(pl.Utf8))

    df = df.rename({_normalise_header(c): _normalise_header(c) for c in df.columns})
    return _apply_column_mapping(df, column_mapping or {})


def read_raw_bytes(
    content: bytes,
    *,
    filename: str,
    column_mapping: dict[str, str] | None = None,
) -> pl.DataFrame:
    """Read from in-memory bytes (used by the upload API)."""
    path = Path(filename)
    fmt = detect_format(path, content=content)
    if fmt == InputFormat.CSV:
        df = pl.read_csv(io.BytesIO(content), infer_schema_length=0)
    elif fmt == InputFormat.XLSX:
        df = pl.read_excel(io.BytesIO(content), infer_schema_length=0)
    else:
        df = pl.read_parquet(io.BytesIO(content))
        if df.schema.get("ts") is not None and "timestamp" not in df.columns:
            df = df.rename({"ts": "timestamp"})
        for col in df.columns:
            df = df.with_columns(pl.col(col).cast(pl.Utf8))

    df = df.rename({_normalise_header(c): _normalise_header(c) for c in df.columns})
    return _apply_column_mapping(df, column_mapping or {})


def infer_columns(path: Path, *, content: bytes | None = None) -> dict[str, object]:
    """Preview detected columns and suggested mapping for the import wizard."""
    df = (
        read_raw_bytes(content, filename=path.name)
        if content is not None
        else read_raw(path)
    )
    sample = df.head(5).to_dicts()
    rename = _build_column_rename(list(df.columns))
    return {
        "columns": list(df.columns),
        "suggested_mapping": {v: k for k, v in rename.items()},
        "sample_rows": sample,
        "row_count_estimate": df.height,
    }
