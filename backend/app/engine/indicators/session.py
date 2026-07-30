"""Session-aware helpers for intraday strategies.

Bars carry UTC epoch milliseconds (ARCHITECTURE.md 2.3), but "the opening
range" and "flatten before the close" are statements about *exchange local*
time. The engine is never told which exchange a dataset belongs to, so the
timezone is a strategy parameter and the conversion happens here - which keeps
the execution layer free of calendar concerns and makes the assumption visible
in the parameter editor instead of buried in code.

No holiday calendar: a session is simply "bars sharing the same local
calendar date". A day the exchange was shut contributes no bars, so it needs no
special handling; a half-day still works because the session is derived from
the data rather than from a schedule.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.engine.bars import Bar
from app.engine.errors import EngineError
from app.engine.indicators.base import Indicator

#: Exchange timezones offered as choices in the parameter editor. Curated
#: rather than free text so the auto-generated form stays a dropdown and an
#: unresolvable zone can never reach the engine.
#:
#: Every entry must be a canonical IANA zone name, not an exchange's city:
#: ``Europe/Frankfurt`` reads plausibly and does not exist, so Xetra is listed
#: under ``Europe/Berlin``. ``test_every_offered_session_timezone_resolves``
#: enforces this.
SESSION_TIMEZONES: tuple[tuple[str, str], ...] = (
    ("UTC", "UTC"),
    ("Asia/Kolkata", "India (NSE/BSE)"),
    ("America/New_York", "US East (NYSE/Nasdaq)"),
    ("America/Chicago", "US Central (CME)"),
    ("Europe/London", "London (LSE)"),
    ("Europe/Berlin", "Frankfurt (Xetra)"),
    ("Europe/Zurich", "Zurich (SIX)"),
    ("Asia/Tokyo", "Tokyo (TSE)"),
    ("Asia/Shanghai", "Shanghai (SSE)"),
    ("Asia/Hong_Kong", "Hong Kong (HKEX)"),
    ("Asia/Singapore", "Singapore (SGX)"),
    ("Australia/Sydney", "Sydney (ASX)"),
    ("Asia/Dubai", "Dubai (DFM)"),
    ("America/Sao_Paulo", "Sao Paulo (B3)"),
)


def resolve_zone(name: str) -> ZoneInfo:
    """Look up a timezone, failing with an engine error rather than a stdlib one."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise EngineError(f"Unknown session timezone '{name}'") from exc


def minutes_of_day(value: str) -> int:
    """Turn a validated ``HH:MM`` parameter into minutes past local midnight."""
    hours, _, minutes = value.partition(":")
    return int(hours) * 60 + int(minutes)


class SessionClock:
    """Maps bars to exchange-local time and flags the first bar of a session."""

    __slots__ = ("_bars_in_session", "_local", "_session_date", "_zone")

    def __init__(self, timezone: str) -> None:
        self._zone = resolve_zone(timezone)
        self._session_date: str | None = None
        self._local: datetime | None = None
        self._bars_in_session = 0

    def advance(self, bar: Bar) -> bool:
        """Point the clock at ``bar``. Returns True if it starts a new session."""
        self._local = datetime.fromtimestamp(bar.ts / 1000, tz=UTC).astimezone(self._zone)
        date_key = self._local.date().isoformat()
        is_new = date_key != self._session_date
        self._session_date = date_key
        self._bars_in_session = 1 if is_new else self._bars_in_session + 1
        return is_new

    @property
    def local_time(self) -> datetime:
        if self._local is None:
            raise EngineError("SessionClock read before the first bar")
        return self._local

    @property
    def minutes_into_day(self) -> int:
        local = self.local_time
        return local.hour * 60 + local.minute

    @property
    def session_date(self) -> str:
        if self._session_date is None:
            raise EngineError("SessionClock read before the first bar")
        return self._session_date

    @property
    def bars_in_session(self) -> int:
        return self._bars_in_session

    def is_at_or_after(self, hhmm: str) -> bool:
        return self.minutes_into_day >= minutes_of_day(hhmm)

    def is_before(self, hhmm: str) -> bool:
        return self.minutes_into_day < minutes_of_day(hhmm)


class OpeningRange(Indicator):
    """High and low of the first ``range_minutes`` of each session.

    Publishes nothing until the range window has *closed* - a range that is
    still forming is not a level, and breaking out of a partially formed range
    is the classic way an opening-range backtest invents edge that never
    existed. Values reset to ``None`` at the start of each new session.
    """

    outputs: ClassVar[tuple[str, ...]] = ("high", "low", "middle", "width")

    def __init__(self, *, timezone: str, session_start: str, range_minutes: int) -> None:
        super().__init__()
        self._clock = SessionClock(timezone)
        self._start_minute = minutes_of_day(session_start)
        self._range_minutes = range_minutes
        self._high: float | None = None
        self._low: float | None = None
        self._is_complete = False

    @property
    def warmup_bars(self) -> int:
        # Driven by wall-clock, not bar count: the first session in a dataset
        # may already be past its opening range, in which case the first usable
        # signal is the next session.
        return 0

    @property
    def is_complete(self) -> bool:
        """True once this session's range window has closed and has values."""
        return self._is_complete

    @property
    def clock(self) -> SessionClock:
        return self._clock

    def _compute(self, bar: Bar) -> None:
        if self._clock.advance(bar):
            self._high = None
            self._low = None
            self._is_complete = False
            self._publish_all(high=None, low=None, middle=None, width=None)

        minute = self._clock.minutes_into_day
        range_end = self._start_minute + self._range_minutes

        if self._start_minute <= minute < range_end:
            self._high = bar.high if self._high is None else max(self._high, bar.high)
            self._low = bar.low if self._low is None else min(self._low, bar.low)
            # Still forming: deliberately publish nothing.
            self._publish_all(high=None, low=None, middle=None, width=None)
            return

        if minute >= range_end and self._high is not None and self._low is not None:
            self._is_complete = True
            self._publish_all(
                high=self._high,
                low=self._low,
                middle=(self._high + self._low) / 2.0,
                width=self._high - self._low,
            )
            return

        self._publish_all(high=None, low=None, middle=None, width=None)
