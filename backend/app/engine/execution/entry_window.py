"""Exchange-local entry windows for execution-level run settings."""

from __future__ import annotations

import re

from app.engine.indicators.session import minutes_of_day

_HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def normalize_hhmm(value: str) -> str:
    """Validate and normalise a 24-hour ``HH:MM`` string."""
    match = _HHMM.match(value.strip())
    if match is None:
        raise ValueError("time must be a 24-hour HH:MM value between 00:00 and 23:59")
    return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"


def validate_entry_window(start: str | None, end: str | None) -> tuple[str, str] | None:
    """Return a normalised window or ``None`` when unset. Raises on invalid input."""
    if start is None and end is None:
        return None
    if start is None or end is None:
        raise ValueError("entry_window_start and entry_window_end must both be provided")
    normalised_start = normalize_hhmm(start)
    normalised_end = normalize_hhmm(end)
    if minutes_of_day(normalised_start) > minutes_of_day(normalised_end):
        raise ValueError("entry_window_start must be at or before entry_window_end")
    return normalised_start, normalised_end


def entry_window_allows(*, minutes_into_day: int, start: str, end: str) -> bool:
    """Whether a bar's local time sits inside an inclusive ``[start, end]`` window."""
    start_minutes = minutes_of_day(start)
    end_minutes = minutes_of_day(end)
    return start_minutes <= minutes_into_day <= end_minutes
