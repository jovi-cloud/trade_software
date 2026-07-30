"""Backward-compatible validator shim.

New code should use ``app.data.data_pipeline`` directly.
"""

from __future__ import annotations

import polars as pl

from app.data.data_pipeline.cleaner import clean_raw
from app.data.data_pipeline.report import ValidationReport as PipelineValidationReport
from app.data.data_pipeline.validators import validate_and_normalise
from app.domain.enums import Timeframe

# Re-export for tests and legacy imports.
ValidationReport = PipelineValidationReport


def validate_and_clean(
    raw: pl.DataFrame, timeframe: Timeframe
) -> tuple[pl.DataFrame, PipelineValidationReport]:
    """Validate raw string-typed bars using the production pipeline."""
    cleaned, _ = clean_raw(raw, remove_duplicates=True)
    return validate_and_normalise(cleaned, timeframe=timeframe, remove_duplicate_timestamps=True)
