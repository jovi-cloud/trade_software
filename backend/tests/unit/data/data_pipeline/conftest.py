"""Shared fixtures for data pipeline tests."""

from __future__ import annotations

import polars as pl
import pytest

from app.data.data_pipeline.metadata import PipelineConfig, SessionConfig
from app.domain.enums import Timeframe

VALID_ROWS = [
    {
        "timestamp": "2024-01-01 09:15:00",
        "open": "100",
        "high": "101",
        "low": "99",
        "close": "100.5",
        "volume": "1000",
    },
    {
        "timestamp": "2024-01-01 09:16:00",
        "open": "100.5",
        "high": "102",
        "low": "100",
        "close": "101.5",
        "volume": "1200",
    },
    {
        "timestamp": "2024-01-01 09:17:00",
        "open": "101.5",
        "high": "103",
        "low": "101",
        "close": "102.5",
        "volume": "900",
    },
]


@pytest.fixture
def valid_df() -> pl.DataFrame:
    return pl.DataFrame(VALID_ROWS)


@pytest.fixture
def pipeline_config() -> PipelineConfig:
    return PipelineConfig(
        timeframe=Timeframe.M1,
        session=SessionConfig(timezone="UTC", open_time="09:15", close_time="15:30"),
        instrument="NIFTY",
        exchange="NSE",
    )
