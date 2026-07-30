"""The bar object and sequential replay.

``Bar`` mirrors the canonical schema the data layer writes (ARCHITECTURE.md
2.3): ``ts`` is int64 UTC epoch milliseconds, prices and volume are float64.

The engine never reads Parquet itself. ``app.data.loader`` does that and hands
plain rows in - which is what keeps the engine importable as a standalone
library with no I/O stack attached (ARCHITECTURE.md principle 3).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from app.engine.errors import EngineError

BAR_FIELDS: tuple[str, ...] = ("ts", "open", "high", "low", "close", "volume")


@dataclass(frozen=True, slots=True)
class Bar:
    """One OHLCV bar. Immutable: a strategy must never be able to rewrite history."""

    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def timestamp(self) -> datetime:
        """UTC datetime view of ``ts``, for strategies doing calendar logic."""
        return datetime.fromtimestamp(self.ts / 1000, tz=UTC)


def bar_from_row(row: Mapping[str, object]) -> Bar:
    """Build a ``Bar`` from a plain mapping, failing loudly on a bad row."""
    try:
        return Bar(
            ts=int(row["ts"]),  # type: ignore[call-overload]
            open=float(row["open"]),  # type: ignore[arg-type]
            high=float(row["high"]),  # type: ignore[arg-type]
            low=float(row["low"]),  # type: ignore[arg-type]
            close=float(row["close"]),  # type: ignore[arg-type]
            volume=float(row["volume"]),  # type: ignore[arg-type]
        )
    except KeyError as exc:
        raise EngineError(f"Bar row is missing the {exc} column") from exc
    except (TypeError, ValueError) as exc:
        raise EngineError(f"Bar row has a non-numeric value: {exc}") from exc


class BarIterator:
    """Forward-only replay over a fixed set of bars.

    Forward-only by construction: no seek, no indexing, no way to reach a
    later bar. That is the structural half of the lookahead prevention
    ARCHITECTURE.md 2.2 requires - a strategy cannot peek ahead because the
    API to do so does not exist.

    Bars may be held in a sequence or arrive from a stream. A streamed source
    is consumable exactly once and declares its length up front, so the engine
    can report progress without having counted the bars itself. Forward-only
    already forbade revisiting a bar; streaming makes that a property of memory
    as well as of the API.
    """

    def __init__(self, bars: Sequence[Bar]) -> None:
        self._bars: Sequence[Bar] | None = bars
        self._stream: Iterator[Bar] | None = None
        self._count = len(bars)

    @classmethod
    def from_rows(cls, rows: Iterable[Mapping[str, object]]) -> BarIterator:
        return cls([bar_from_row(row) for row in rows])

    @classmethod
    def streaming(cls, bars: Iterable[Bar], *, count: int) -> BarIterator:
        """Replay ``count`` bars from a single-pass source.

        ``count`` is supplied because a stream cannot be measured without
        draining it, and the bar loop needs the total to report progress.
        """
        if count < 0:
            raise EngineError("Bar count must not be negative")
        iterator = cls.__new__(cls)
        iterator._bars = None
        iterator._stream = iter(bars)
        iterator._count = count
        return iterator

    @property
    def is_streaming(self) -> bool:
        return self._bars is None

    def __len__(self) -> int:
        return self._count

    def __iter__(self) -> Iterator[Bar]:
        if self._bars is not None:
            return iter(self._bars)
        if self._stream is None:
            raise EngineError(
                "This BarIterator streams its bars and has already been replayed; "
                "build a new one to run again"
            )
        stream, self._stream = self._stream, None
        return stream
