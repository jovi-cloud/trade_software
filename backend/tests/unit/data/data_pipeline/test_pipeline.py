"""End-to-end pipeline tests."""

from __future__ import annotations

import polars as pl

from app.data.data_pipeline.cleaner import clean_raw
from app.data.data_pipeline.metadata import PipelineConfig, SessionConfig
from app.data.data_pipeline.pipeline import _run_pipeline
from app.domain.enums import Timeframe


def test_pipeline_produces_high_quality_score(valid_df: pl.DataFrame, pipeline_config: PipelineConfig) -> None:
    result = _run_pipeline(valid_df, pipeline_config)
    assert result.report.quality_score >= 95
    assert not result.report.rejected
    assert result.bars.height == 3


def test_pipeline_rejects_inconsistent_timeframe() -> None:
    df = pl.DataFrame(
        {
            "timestamp": [
                "2024-01-01 09:15:00",
                "2024-01-01 09:16:00",
                "2024-01-01 09:25:00",
            ],
            "open": ["100", "100", "100"],
            "high": ["101", "101", "101"],
            "low": ["99", "99", "99"],
            "close": ["100", "100", "100"],
            "volume": ["1000", "1000", "1000"],
        }
    )
    config = PipelineConfig(timeframe=None, session=SessionConfig())
    result = _run_pipeline(df, config)
    assert result.report.rejected
    assert result.report.quality_score < 70


def test_cleaner_reports_blank_row_removal() -> None:
    df = pl.DataFrame(
        {
            "timestamp": ["2024-01-01 09:15:00", "", "2024-01-01 09:17:00"],
            "open": ["100", "101", "101.5"],
            "high": ["101", "102", "103"],
            "low": ["99", "100", "101"],
            "close": ["100.5", "101.5", "102.5"],
            "volume": ["1000", "1200", "900"],
        }
    )
    cleaned, report = clean_raw(df)
    assert cleaned.height == 2
    assert any(a.action == "remove_blank_rows" for a in report.actions)
