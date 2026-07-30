"""Serialise pipeline reports to JSON-compatible dicts."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import StrEnum


def _encode_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _encode_value(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {k: _encode_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode_value(v) for v in value]
    return value


def pipeline_report_to_dict(report: object) -> dict[str, object]:
    return _encode_value(report)  # type: ignore[return-value]
