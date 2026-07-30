"""Unit tests for dataset fingerprint generation."""

from __future__ import annotations

import polars as pl

from app.data.fingerprint import compute_dataset_fingerprint


def test_empty_bars_have_stable_fingerprint() -> None:
    empty = pl.DataFrame(
        {
            "ts": [],
            "open": [],
            "high": [],
            "low": [],
            "close": [],
            "volume": [],
        }
    )
    assert compute_dataset_fingerprint(empty, timeframe="1m", timezone="UTC")


def test_fingerprint_changes_when_bars_change() -> None:
    bars_a = pl.DataFrame(
        {
            "ts": [1],
            "open": [1.0],
            "high": [1.0],
            "low": [1.0],
            "close": [1.0],
            "volume": [1.0],
        }
    )
    bars_b = pl.DataFrame(
        {
            "ts": [1],
            "open": [2.0],
            "high": [2.0],
            "low": [2.0],
            "close": [2.0],
            "volume": [1.0],
        }
    )
    first = compute_dataset_fingerprint(bars_a, timeframe="1m", timezone="UTC")
    second = compute_dataset_fingerprint(bars_b, timeframe="1m", timezone="UTC")
    assert first != second
