"""Tests for exchange-local entry windows."""

from __future__ import annotations

import pytest

from app.engine.execution.entry_window import (
    entry_window_allows,
    normalize_hhmm,
    validate_entry_window,
)


def test_normalize_hhmm_accepts_valid_values() -> None:
    assert normalize_hhmm("09:15") == "09:15"
    assert normalize_hhmm("15:25") == "15:25"


def test_validate_entry_window_requires_both_bounds() -> None:
    with pytest.raises(ValueError, match="both be provided"):
        validate_entry_window("09:15", None)


def test_validate_entry_window_rejects_inverted_range() -> None:
    with pytest.raises(ValueError, match="at or before"):
        validate_entry_window("15:00", "09:15")


def test_entry_window_allows_inclusive_bounds() -> None:
    assert entry_window_allows(minutes_into_day=9 * 60 + 15, start="09:15", end="15:25")
    assert entry_window_allows(minutes_into_day=15 * 60 + 25, start="09:15", end="15:25")
    assert not entry_window_allows(minutes_into_day=9 * 60 + 14, start="09:15", end="15:25")
    assert not entry_window_allows(minutes_into_day=15 * 60 + 26, start="09:15", end="15:25")
