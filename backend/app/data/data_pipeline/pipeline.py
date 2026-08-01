"""Market data pipeline orchestrator.

Raw file -> validate -> clean -> normalise -> session check -> gap detection
-> statistics -> quality score -> canonical bars + reports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from app.data.data_pipeline.cleaner import clean_raw
from app.data.data_pipeline.gap_detector import detect_gaps
from app.data.data_pipeline.importer import read_raw, read_raw_bytes
from app.data.data_pipeline.metadata import PipelineConfig
from app.data.data_pipeline.price_anomaly_cleaner import clean_price_anomaly_days
from app.data.data_pipeline.price_anomaly_detector import detect_price_anomalies
from app.data.data_pipeline.quality import build_pipeline_report
from app.data.data_pipeline.report import CleaningReport, PipelineReport
from app.data.data_pipeline.session_cleaner import clean_session_bars
from app.data.data_pipeline.session_validator import validate_session
from app.data.data_pipeline.statistics import compute_statistics, detect_timeframe
from app.data.data_pipeline.validators import validate_and_normalise
from app.data.errors import MissingColumnsError


@dataclass(frozen=True)
class PipelineResult:
    bars: pl.DataFrame
    report: PipelineReport


def run_pipeline_from_path(path: Path, config: PipelineConfig) -> PipelineResult:
    """Run the full pipeline on a file path."""
    try:
        raw = read_raw(path, column_mapping=dict(config.column_mapping))
    except MissingColumnsError:
        raise
    return _run_pipeline(raw, config)


def run_pipeline_from_bytes(
    content: bytes,
    *,
    filename: str,
    config: PipelineConfig,
) -> PipelineResult:
    """Run the full pipeline on uploaded bytes."""
    try:
        raw = read_raw_bytes(content, filename=filename, column_mapping=dict(config.column_mapping))
    except MissingColumnsError:
        raise
    return _run_pipeline(raw, config)


def _run_pipeline(raw: pl.DataFrame, config: PipelineConfig) -> PipelineResult:
    cleaned, cleaning_report = clean_raw(raw, remove_duplicates=config.remove_duplicate_rows)
    bars, validation = validate_and_normalise(
        cleaned,
        timeframe=config.timeframe,
        remove_duplicate_timestamps=True,
        timezone=config.session.timezone,
    )

    price_anomaly_report = detect_price_anomalies(bars, session=config.session)
    if config.session_cleaning.price_anomaly_cleaning_enabled:
        bars, anomaly_cleaning = clean_price_anomaly_days(
            bars,
            price_anomaly_report,
            config.session,
            config.session_cleaning,
        )
        cleaning_report = CleaningReport(
            actions=cleaning_report.actions + anomaly_cleaning.actions
        )
        price_anomaly_report = detect_price_anomalies(bars, session=config.session)
        validation_updates: dict[str, object] = {"valid_rows": bars.height}
        if bars.height > 0:
            min_ts = int(bars.select(pl.col("ts").min()).item())
            max_ts = int(bars.select(pl.col("ts").max()).item())
            validation_updates["start_date"] = datetime.fromtimestamp(min_ts / 1000, tz=UTC)
            validation_updates["end_date"] = datetime.fromtimestamp(max_ts / 1000, tz=UTC)
        validation = type(validation)(**{**validation.__dict__, **validation_updates})

    if config.session_cleaning.enabled and (
        config.session_cleaning.remove_outside_session
        or config.session_cleaning.remove_weekend_bars
        or config.session_cleaning.remove_holiday_bars
    ):
        bars, session_cleaning = clean_session_bars(
            bars, config.session, config.session_cleaning
        )
        cleaning_report = CleaningReport(
            actions=cleaning_report.actions + session_cleaning.actions
        )
        validation_updates: dict[str, object] = {"valid_rows": bars.height}
        if bars.height > 0:
            min_ts = int(bars.select(pl.col("ts").min()).item())
            max_ts = int(bars.select(pl.col("ts").max()).item())
            validation_updates["start_date"] = datetime.fromtimestamp(min_ts / 1000, tz=UTC)
            validation_updates["end_date"] = datetime.fromtimestamp(max_ts / 1000, tz=UTC)
        validation = type(validation)(**{**validation.__dict__, **validation_updates})

    timeframe_report = detect_timeframe(bars)
    resolved_timeframe = config.timeframe or timeframe_report.detected

    session_report = validate_session(bars, config.session)
    gap_report = detect_gaps(
        bars,
        timeframe=resolved_timeframe,
        dominant_interval_ms=timeframe_report.dominant_interval_ms,
        session=config.session,
    )

    # Update validation with gap counts from dedicated detector.
    validation = type(validation)(
        **{
            **validation.__dict__,
            "missing_timestamps": gap_report.missing_bars,
            "gap_samples": gap_report.missing_timestamps,
        }
    )

    quality_score = 0
    statistics = compute_statistics(
        bars,
        instrument=config.instrument,
        timeframe=resolved_timeframe.value if resolved_timeframe else None,
        missing_bars=gap_report.missing_bars,
        duplicate_bars=gap_report.duplicate_bars,
        gap_percentage=gap_report.gap_percentage,
        quality_score=quality_score,
    )

    report = build_pipeline_report(
        validation=validation,
        cleaning=cleaning_report,
        session=session_report,
        gaps=gap_report,
        timeframe=timeframe_report,
        statistics=statistics,
        price_anomalies=price_anomaly_report,
    )

    # Recompute statistics with final quality score.
    statistics = compute_statistics(
        bars,
        instrument=config.instrument,
        timeframe=resolved_timeframe.value if resolved_timeframe else None,
        missing_bars=gap_report.missing_bars,
        duplicate_bars=gap_report.duplicate_bars,
        gap_percentage=gap_report.gap_percentage,
        quality_score=report.quality_score,
    )
    report = type(report)(
        **{**report.__dict__, "statistics": statistics}
    )

    return PipelineResult(bars=bars, report=report)
