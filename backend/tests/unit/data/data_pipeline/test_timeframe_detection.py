"""Tests for timeframe detection."""

from __future__ import annotations

import polars as pl

from app.data.data_pipeline.statistics import detect_timeframe
from app.domain.enums import Timeframe


def test_detect_timeframe_1m() -> None:
    base = 1_704_105_300_000
    bars = pl.DataFrame({"ts": [base + i * 60_000 for i in range(10)]})
    report = detect_timeframe(bars)
    assert report.detected == Timeframe.M1
    assert report.is_consistent


def test_detect_timeframe_rejects_inconsistent() -> None:
    base = 1_704_105_300_000
    ts = [base, base + 60_000, base + 120_000, base + 420_000, base + 480_000]
    bars = pl.DataFrame({"ts": ts})
    report = detect_timeframe(bars)
    assert not report.is_consistent
