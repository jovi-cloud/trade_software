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
    """

    def __init__(self, bars: Sequence[Bar]) -> None:
        self._bars = bars

    @classmethod
    def from_rows(cls, rows: Iterable[Mapping[str, object]]) -> BarIterator:
        return cls([bar_from_row(row) for row in rows])

    def __len__(self) -> int:
        return len(self._bars)

    def __iter__(self) -> Iterator[Bar]:
        return iter(self._bars)
