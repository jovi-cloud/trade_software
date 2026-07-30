"""The indicator contract.

Indicators here are **incremental**, not vectorised. The engine replays bars
forward-only and a strategy can never see a later bar (``BarIterator`` has no
seek and no indexing), so an indicator that could only be computed over a whole
series would either need lookahead or a second pass. Feeding one bar at a time
makes lookahead impossible by construction rather than by convention, which is
the same guarantee ARCHITECTURE.md 2.2 makes about fills.

Cost model: every indicator below updates in O(1) or O(window) per bar with no
allocation in the steady state, so the bar loop stays linear in bar count.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from typing import ClassVar

from app.engine.bars import Bar

#: The output name every single-valued indicator publishes.
PRIMARY_OUTPUT = "value"


class Indicator(ABC):
    """A stateful, forward-only transform of a bar stream.

    Subclasses declare their output names and implement ``_compute``. Multi-
    output indicators (Bollinger, MACD, SuperTrend) publish several named
    values from one update so their internals are shared rather than
    recomputed per output.
    """

    #: Output names, primary first. Single-output indicators keep the default.
    outputs: ClassVar[tuple[str, ...]] = (PRIMARY_OUTPUT,)

    def __init__(self) -> None:
        self._values: dict[str, float | None] = dict.fromkeys(self.outputs)
        self._bars_seen = 0

    # -- contract ---------------------------------------------------------
    @property
    @abstractmethod
    def warmup_bars(self) -> int:
        """Bars required before this indicator can publish a value."""

    @abstractmethod
    def _compute(self, bar: Bar) -> None:
        """Fold ``bar`` into internal state and call ``_publish``."""

    # -- driving ----------------------------------------------------------
    def update(self, bar: Bar) -> None:
        self._bars_seen += 1
        self._compute(bar)

    def _publish(self, name: str, value: float | None) -> None:
        self._values[name] = value

    def _publish_all(self, **values: float | None) -> None:
        for name, value in values.items():
            self._values[name] = value

    # -- reading ----------------------------------------------------------
    @property
    def bars_seen(self) -> int:
        return self._bars_seen

    @property
    def value(self) -> float | None:
        """The primary output, or ``None`` while warming up."""
        return self._values[self.outputs[0]]

    @property
    def is_ready(self) -> bool:
        """True once every declared output has a value."""
        return all(value is not None for value in self._values.values())

    def output(self, name: str) -> float | None:
        try:
            return self._values[name]
        except KeyError:
            raise KeyError(
                f"{type(self).__name__} has no output '{name}'; "
                f"available: {', '.join(self.outputs)}"
            ) from None

    def snapshot(self) -> dict[str, float | None]:
        return dict(self._values)


class RollingWindow:
    """Fixed-size window with O(1) mean and variance.

    Mean and variance come from running sums rather than a fresh pass over the
    window: an indicator on a multi-million-bar dataset is updated once per
    bar, and an O(window) recompute there is the difference between a run that
    takes a second and one that takes a minute. Running sums drift by a few
    ULPs versus an exact pass; that is deterministic (identical input gives
    identical output, which is what reproducibility requires) and far below the
    tick size of any instrument.
    """

    __slots__ = ("_items", "_size", "_sum", "_sum_squares")

    def __init__(self, size: int) -> None:
        if size < 1:
            raise ValueError("Rolling window size must be at least 1")
        self._size = size
        self._items: deque[float] = deque(maxlen=size)
        self._sum = 0.0
        self._sum_squares = 0.0

    def append(self, value: float) -> None:
        if len(self._items) == self._size:
            evicted = self._items[0]
            self._sum -= evicted
            self._sum_squares -= evicted * evicted
        self._items.append(value)
        self._sum += value
        self._sum_squares += value * value

    def __len__(self) -> int:
        return len(self._items)

    @property
    def size(self) -> int:
        return self._size

    @property
    def is_full(self) -> bool:
        return len(self._items) == self._size

    @property
    def items(self) -> tuple[float, ...]:
        return tuple(self._items)

    @property
    def first(self) -> float:
        return self._items[0]

    @property
    def last(self) -> float:
        return self._items[-1]

    @property
    def total(self) -> float:
        return self._sum

    def mean(self) -> float | None:
        if not self.is_full:
            return None
        return self._sum / self._size

    def variance(self) -> float | None:
        """Population variance (ddof=0), the convention Bollinger Bands use."""
        if not self.is_full:
            return None
        mean = self._sum / self._size
        # Clamped: catastrophic cancellation on a flat window can produce a
        # tiny negative value, and sqrt of that would raise.
        return max(0.0, self._sum_squares / self._size - mean * mean)

    def highest(self) -> float | None:
        if not self._items:
            return None
        return max(self._items)

    def lowest(self) -> float | None:
        if not self._items:
            return None
        return min(self._items)
