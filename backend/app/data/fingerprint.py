"""Deterministic fingerprint of cleaned bar data.

The fingerprint identifies the actual cleaned dataset content, not the
uploaded file. Two different source files that normalize to identical bars
produce the same fingerprint.
"""

from __future__ import annotations

import hashlib
import json
import struct

import polars as pl

from app.domain.enums import Timeframe


def compute_dataset_fingerprint(
    bars: pl.DataFrame,
    *,
    timeframe: str,
    timezone: str,
) -> str:
    """SHA-256 hex digest over canonical cleaned-bar metadata and OHLCV checksum."""
    if bars.is_empty():
        payload = {
            "row_count": 0,
            "first_ts": None,
            "last_ts": None,
            "ohlcv_checksum": "",
            "timeframe": timeframe,
            "timezone": timezone,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    sorted_bars = bars.sort("ts")
    first_ts = int(sorted_bars["ts"][0])
    last_ts = int(sorted_bars["ts"][-1])
    ohlcv_checksum = _ohlcv_checksum(sorted_bars)

    payload = {
        "row_count": sorted_bars.height,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "ohlcv_checksum": ohlcv_checksum,
        "timeframe": timeframe,
        "timezone": timezone,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _ohlcv_checksum(bars: pl.DataFrame) -> str:
    """Stable checksum over canonical OHLCV columns in row order."""
    digest = hashlib.sha256()
    for column in ("ts", "open", "high", "low", "close", "volume"):
        series = bars[column]
        if series.dtype in (pl.Float32, pl.Float64):
            values = series.cast(pl.Float64).to_numpy()
            digest.update(struct.pack(f"<{len(values)}d", *values))
        else:
            values = series.cast(pl.Int64).to_numpy()
            digest.update(struct.pack(f"<{len(values)}q", *values))
    return digest.hexdigest()


def resolve_timeframe_label(timeframe: str | Timeframe | None, detected: str | None) -> str:
    """Pick the canonical timeframe string used in a fingerprint."""
    if timeframe:
        return timeframe.value if isinstance(timeframe, Timeframe) else timeframe
    return detected or Timeframe.M1.value
