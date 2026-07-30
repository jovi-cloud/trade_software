"""Dataset request/response DTOs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import DatasetLifecycle, DatasetStatus, ImportStatus, Timeframe

NAME_MAX_LENGTH = 200
SYMBOL_MAX_LENGTH = 50
EXCHANGE_MAX_LENGTH = 50


class CleaningActionRead(BaseModel):
    action: str
    count: int
    detail: str = ""


class CleaningReportRead(BaseModel):
    actions: list[CleaningActionRead] = Field(default_factory=list)


class DatasetValidationReport(BaseModel):
    """Row-level validation summary (nested inside the full pipeline report)."""

    model_config = ConfigDict(from_attributes=True)

    total_rows: int
    valid_rows: int
    invalid_dates: int
    invalid_prices: int
    duplicate_timestamps: int
    missing_timestamps: int
    out_of_order_timestamps: int = 0
    ohlc_violations: int = 0
    negative_volumes: int = 0
    non_positive_prices: int = 0
    nan_values: int = 0
    infinity_values: int = 0
    start_date: datetime | None
    end_date: datetime | None
    duplicate_samples: tuple[str, ...] = ()
    gap_samples: tuple[str, ...] = ()


class SessionReportRead(BaseModel):
    missing_opening_candles: int = 0
    missing_closing_candles: int = 0
    candles_outside_session: int = 0
    unexpected_weekend_bars: int = 0
    unexpected_holiday_bars: int = 0
    outside_session_samples: tuple[str, ...] = ()


class GapReportRead(BaseModel):
    expected_bars: int
    actual_bars: int
    missing_bars: int
    duplicate_bars: int
    large_jumps: int = 0
    partial_trading_days: int = 0
    gap_percentage: float
    missing_timestamps: tuple[str, ...] = ()
    large_jump_samples: tuple[str, ...] = ()


class TimeframeReportRead(BaseModel):
    detected: Timeframe | None = None
    is_consistent: bool = True
    dominant_interval_ms: int | None = None
    inconsistent_intervals: int = 0


class DatasetStatisticsRead(BaseModel):
    date_range_start: datetime | None
    date_range_end: datetime | None
    total_bars: int
    trading_days: int
    average_daily_bars: float
    min_price: float | None
    max_price: float | None
    average_volume: float | None
    timeframe: str | None
    instrument: str
    missing_bars: int
    duplicate_bars: int
    gap_percentage: float
    quality_score: int


class PipelineReportRead(BaseModel):
    """Full import pipeline report persisted on each dataset."""

    validation: DatasetValidationReport
    cleaning: CleaningReportRead = Field(default_factory=CleaningReportRead)
    session: SessionReportRead = Field(default_factory=SessionReportRead)
    gaps: GapReportRead | None = None
    timeframe: TimeframeReportRead | None = None
    statistics: DatasetStatisticsRead | None = None
    quality_score: int = 0
    rejected: bool = False
    rejection_reason: str | None = None


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    symbol: str
    exchange: str
    timeframe: Timeframe
    file_path: str
    original_filename: str | None = None
    file_hash: str | None = None
    timezone: str = "UTC"
    detected_timeframe: Timeframe | None = None
    quality_score: int | None = None
    row_count: int
    start_date: datetime | None
    end_date: datetime | None
    status: DatasetStatus
    lifecycle: DatasetLifecycle = DatasetLifecycle.ACTIVE
    import_status: ImportStatus
    current_version_id: str | None = None
    current_version_number: int | None = None
    version_count: int = 0
    validation_report: DatasetValidationReport | None
    pipeline_report: PipelineReportRead | None = None
    # Set only when the import failed before validation could run.
    import_error: str | None
    created_at: datetime
    updated_at: datetime


class DatasetVersionRead(BaseModel):
    id: str
    dataset_id: str
    version_number: int
    data_import_id: str | None = None
    file_path: str
    file_size_bytes: int
    parquet_hash: str
    fingerprint: str
    row_count: int
    start_date: datetime | None
    end_date: datetime | None
    timezone: str
    detected_timeframe: Timeframe | None = None
    quality_score: int | None = None
    status: str
    error_message: str | None = None
    validation_report: DatasetValidationReport | None = None
    pipeline_report: PipelineReportRead | None = None
    created_at: datetime


class DatasetBacktestReference(BaseModel):
    run_id: str
    strategy_name: str
    dataset_version_number: int | None = None
    execution_completed_at: datetime


class DatasetReferencesRead(BaseModel):
    reference_count: int
    backtest_runs: list[DatasetBacktestReference]


class BarRow(BaseModel):
    ts: int = Field(description="UTC epoch milliseconds")
    open: float
    high: float
    low: float
    close: float
    volume: float


class DatasetPreview(BaseModel):
    rows: list[BarRow]


class ImportPreviewResponse(BaseModel):
    columns: list[str]
    suggested_mapping: dict[str, str]
    sample_rows: list[dict[str, object]]
    row_count_estimate: int


class DataImportRead(BaseModel):
    id: str
    dataset_id: str
    dataset_version_id: str | None = None
    filename: str
    file_hash: str
    rows_read: int
    rows_written: int
    rows_rejected: int
    duplicates_removed: int
    gaps_detected: int
    quality_score: int | None
    status: ImportStatus
    error_message: str | None
    report: PipelineReportRead | None = None
    created_at: datetime
