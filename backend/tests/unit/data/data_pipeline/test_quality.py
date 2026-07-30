"""Tests for quality scoring."""

from __future__ import annotations

from app.data.data_pipeline.quality import compute_quality_score, should_reject
from app.data.data_pipeline.report import GapReport, SessionReport, TimeframeReport, ValidationReport
from app.domain.enums import Timeframe


def _validation(**kwargs: object) -> ValidationReport:
    defaults = {
        "total_rows": 100,
        "valid_rows": 100,
        "invalid_dates": 0,
        "invalid_prices": 0,
        "duplicate_timestamps": 0,
        "missing_timestamps": 0,
    }
    defaults.update(kwargs)  # type: ignore[arg-type]
    return ValidationReport(**defaults)  # type: ignore[arg-type]


def test_perfect_score() -> None:
    score = compute_quality_score(
        _validation(),
        GapReport(100, 100, 0, 0, 0, 0, 0.0),
        SessionReport(),
        TimeframeReport(detected=Timeframe.M1, is_consistent=True),
    )
    assert score == 100


def test_reject_below_threshold() -> None:
    validation = _validation(valid_rows=50, invalid_dates=50)
    rejected, reason = should_reject(
        65,
        validation,
        TimeframeReport(detected=Timeframe.M1, is_consistent=True),
    )
    assert rejected
    assert reason is not None
