"""Dataset request/response DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ImportStatus, Timeframe

NAME_MAX_LENGTH = 200
SYMBOL_MAX_LENGTH = 50
EXCHANGE_MAX_LENGTH = 50


class DatasetValidationReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_rows: int
    valid_rows: int
    invalid_dates: int
    invalid_prices: int
    duplicate_timestamps: int
    missing_timestamps: int
    start_date: datetime | None
    end_date: datetime | None
    duplicate_samples: tuple[str, ...] = ()
    gap_samples: tuple[str, ...] = ()


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    symbol: str
    exchange: str
    timeframe: Timeframe
    file_path: str
    row_count: int
    start_date: datetime | None
    end_date: datetime | None
    import_status: ImportStatus
    validation_report: DatasetValidationReport | None
    # Set only when the import failed before validation could run (e.g. missing
    # columns), so the UI can name the actual problem instead of guessing.
    import_error: str | None
    created_at: datetime
    updated_at: datetime


class BarRow(BaseModel):
    ts: int = Field(description="UTC epoch milliseconds")
    open: float
    high: float
    low: float
    close: float
    volume: float


class DatasetPreview(BaseModel):
    rows: list[BarRow]
