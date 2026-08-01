"""Tests for intraday and cross-day price spike detection."""

from __future__ import annotations

import polars as pl

from app.data.data_pipeline.metadata import SessionConfig
from app.data.data_pipeline.price_anomaly_detector import detect_price_anomalies


def _ts(iso_local: str) -> int:
    # Asia/Kolkata is UTC+5:30 in January.
    from datetime import datetime
    from zoneinfo import ZoneInfo

    dt = datetime.fromisoformat(iso_local).replace(tzinfo=ZoneInfo("Asia/Kolkata"))
    return int(dt.timestamp() * 1000)


def test_detects_intraday_spikes_over_10_and_20_percent() -> None:
    bars = pl.DataFrame(
        {
            "ts": [
                _ts("2024-01-01 09:15:00"),
                _ts("2024-01-01 09:17:00"),
                _ts("2024-01-01 09:19:00"),
                _ts("2024-01-02 09:15:00"),
                _ts("2024-01-02 09:17:00"),
                _ts("2024-01-02 09:19:00"),
            ],
            "open": [100.0, 100.0, 115.0, 125.0, 125.0, 125.0],
            "high": [100.0, 100.0, 116.0, 126.0, 126.0, 160.0],
            "low": [100.0, 100.0, 114.0, 124.0, 124.0, 155.0],
            "close": [100.0, 100.0, 125.0, 125.0, 125.0, 160.0],
            "volume": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        }
    )
    session = SessionConfig(timezone="Asia/Kolkata")

    report = detect_price_anomalies(bars, session=session)

    assert report.spikes_over_10_pct == 2
    assert report.spikes_over_20_pct == 2
    assert report.cross_day_spikes_over_10_pct == 0
    assert report.intraday_days_over_10_samples == ("2024-01-01", "2024-01-02")


def test_detects_cross_day_spikes_between_consecutive_trading_days() -> None:
    bars = pl.DataFrame(
        {
            "ts": [_ts("2024-01-01 15:25:00"), _ts("2024-01-02 09:15:00")],
            "open": [100.0, 200.0],
            "high": [100.0, 200.0],
            "low": [100.0, 200.0],
            "close": [100.0, 200.0],
            "volume": [1.0, 1.0],
        }
    )

    report = detect_price_anomalies(bars, session=SessionConfig(timezone="Asia/Kolkata"))

    assert report.spikes_over_10_pct == 0
    assert report.spikes_over_20_pct == 0
    assert report.cross_day_spikes_over_10_pct == 1
    assert report.cross_day_spikes_over_20_pct == 1
    assert report.cross_day_days_over_10_samples == ("2024-01-01", "2024-01-02")
    assert report.days_over_10_samples == ("2024-01-01", "2024-01-02")
