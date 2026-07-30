"""Deterministic quality scoring for imported datasets."""

from __future__ import annotations

from app.data.data_pipeline.metadata import QUALITY_REJECT_THRESHOLD
from app.data.data_pipeline.report import (
    CleaningReport,
    DatasetStatistics,
    GapReport,
    PipelineReport,
    SessionReport,
    TimeframeReport,
    ValidationReport,
)


def compute_quality_score(
    validation: ValidationReport,
    gaps: GapReport,
    session: SessionReport,
    timeframe: TimeframeReport,
) -> int:
    """Compute a deterministic 0-100 quality score.

    100 = perfect, 95+ minor issues, 80+ recoverable, <70 rejects import.
    """
    if validation.valid_rows == 0:
        return 0
    if not timeframe.is_consistent:
        return min(69, 50)

    score = 100.0
    total = max(validation.total_rows, 1)

    score -= min(15.0, (validation.invalid_dates / total) * 100 * 1.5)
    score -= min(10.0, (validation.invalid_prices / total) * 100)
    score -= min(20.0, (validation.ohlc_violations / total) * 100 * 2.0)
    score -= min(10.0, (validation.negative_volumes / total) * 100)
    score -= min(15.0, (validation.non_positive_prices / total) * 100 * 1.5)
    score -= min(5.0, (validation.duplicate_timestamps / total) * 100 * 0.5)
    score -= min(5.0, (validation.nan_values / total) * 100)
    score -= min(5.0, (validation.infinity_values / total) * 100)
    score -= min(15.0, gaps.gap_percentage * 0.3)
    score -= min(10.0, session.total_issues * 0.2)

    if validation.out_of_order_timestamps > 0:
        score -= 1.0

    return max(0, min(100, round(score)))


def should_reject(
    quality_score: int,
    validation: ValidationReport,
    timeframe: TimeframeReport,
) -> tuple[bool, str | None]:
    if validation.valid_rows == 0:
        return True, "No valid rows after validation"
    if not timeframe.is_consistent:
        return True, "Inconsistent bar intervals detected"
    if quality_score < QUALITY_REJECT_THRESHOLD:
        return (
            True,
            f"Quality score {quality_score} is below the minimum "
            f"threshold of {QUALITY_REJECT_THRESHOLD}",
        )
    return False, None


def build_pipeline_report(
    *,
    validation: ValidationReport,
    cleaning: CleaningReport,
    session: SessionReport,
    gaps: GapReport,
    timeframe: TimeframeReport,
    statistics: DatasetStatistics,
) -> PipelineReport:
    quality_score = compute_quality_score(validation, gaps, session, timeframe)
    rejected, reason = should_reject(quality_score, validation, timeframe)
    return PipelineReport(
        validation=validation,
        cleaning=cleaning,
        session=session,
        gaps=gaps,
        timeframe=timeframe,
        statistics=statistics,
        quality_score=quality_score,
        rejected=rejected,
        rejection_reason=reason,
    )
