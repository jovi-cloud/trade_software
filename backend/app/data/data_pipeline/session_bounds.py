"""Exchange session bar boundary helpers.

Bar timestamps are period *open* times in exchange-local wall clock. For NSE 5m
data the last candle is stamped 15:25 and covers 15:25–15:30, so session
``close_time`` must be the last bar open (15:25), not the market bell (15:30).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionBarBounds:
    """Inclusive first/last bar open times as minutes since midnight."""

    open_minutes: int
    last_bar_minutes: int


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour, minute = value.split(":")
    return int(hour), int(minute)


def minutes_from_hhmm(value: str) -> int:
    hour, minute = _parse_hhmm(value)
    return hour * 60 + minute


def resolve_session_bar_bounds(open_time: str, close_time: str) -> SessionBarBounds:
    """Resolve configured session open/close to bar open-minute bounds."""
    open_minutes = minutes_from_hhmm(open_time)
    last_bar_minutes = minutes_from_hhmm(close_time)
    if last_bar_minutes < open_minutes:
        last_bar_minutes = open_minutes
    return SessionBarBounds(open_minutes=open_minutes, last_bar_minutes=last_bar_minutes)


def is_within_session(minutes: int, bounds: SessionBarBounds) -> bool:
    return bounds.open_minutes <= minutes <= bounds.last_bar_minutes


def matches_bar_time(minutes: int, target_minutes: int, *, tolerance: int = 1) -> bool:
    return abs(minutes - target_minutes) <= tolerance
