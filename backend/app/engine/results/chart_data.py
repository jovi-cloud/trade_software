"""Chart series derived from replayed bars and completed trades.

Pure functions only: no I/O, no metric recomputation. Markers are positioned
from the same trade records the metrics engine already consumed.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from app.domain.enums import PositionSide
from app.engine.bars import Bar, bar_from_row
from app.engine.execution.trade import Trade

MarkerKind = Literal["entry", "exit"]


#: ``slots`` on both series below: there is one candle per bar, so this is the
#: longest-lived per-bar structure in a run. Slots drop the per-instance dict and
#: roughly halve it.
@dataclass(frozen=True, slots=True)
class TrailingStopPoint:
    """One point on the trailing-stop line while a position is open."""

    ts: int
    level: float
    trade_seq: int


@dataclass(frozen=True, slots=True)
class Candle:
    """One OHLCV bar for the price chart."""

    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class TradeMarker:
    """Entry or exit marker anchored to one trade."""

    ts: int
    price: float
    trade_seq: int
    side: PositionSide
    marker_kind: MarkerKind


class TrailingStopCollector:
    """Records trailing-stop levels bar-by-bar for chart overlays."""

    def __init__(self) -> None:
        self._points: list[TrailingStopPoint] = []

    def record(self, *, ts: int, level: float, trade_seq: int) -> None:
        self._points.append(TrailingStopPoint(ts=ts, level=level, trade_seq=trade_seq))

    @property
    def points(self) -> tuple[TrailingStopPoint, ...]:
        return tuple(self._points)


class CandleCollector:
    """Builds the candle series from bars as they stream past.

    The chart needs one candle per bar, so this series is as long as the replay
    however it is built. What it does *not* need is a second and third full copy
    of the bars to build it from: tapping the replay stream leaves exactly one
    materialised per-bar series alive instead of three.

    Only bars actually replayed are collected, so a run that stopped early
    carries candles for what it did rather than for what it was given.
    """

    def __init__(self) -> None:
        self._candles: list[Candle] = []

    def tap(self, bars: Iterable[Bar]) -> Iterator[Bar]:
        """Pass ``bars`` through untouched, recording a candle for each."""
        for bar in bars:
            self._candles.append(
                Candle(
                    ts=bar.ts,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                )
            )
            yield bar

    @property
    def candles(self) -> tuple[Candle, ...]:
        return tuple(self._candles)


class ChartDataBuilder:
    """Builds candle and trade-marker series for visual analysis."""

    def build(
        self,
        bar_rows: Sequence[Mapping[str, object]],
        trades: Sequence[Trade],
    ) -> tuple[tuple[Candle, ...], tuple[TradeMarker, ...], tuple[TradeMarker, ...]]:
        candles = self._candles(bar_rows)
        entry_markers, exit_markers = self._markers(trades)
        return candles, entry_markers, exit_markers

    def markers(
        self, trades: Sequence[Trade]
    ) -> tuple[tuple[TradeMarker, ...], tuple[TradeMarker, ...]]:
        """Entry and exit markers alone, for a run whose candles were streamed."""
        return self._markers(trades)

    def _candles(self, bar_rows: Sequence[Mapping[str, object]]) -> tuple[Candle, ...]:
        candles: list[Candle] = []
        for row in bar_rows:
            bar = bar_from_row(row)
            candles.append(
                Candle(
                    ts=bar.ts,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                )
            )
        return tuple(candles)

    def _markers(
        self, trades: Sequence[Trade]
    ) -> tuple[tuple[TradeMarker, ...], tuple[TradeMarker, ...]]:
        entries: list[TradeMarker] = []
        exits: list[TradeMarker] = []
        for trade in trades:
            entries.append(
                TradeMarker(
                    ts=trade.entry_ts,
                    price=trade.entry_price,
                    trade_seq=trade.seq,
                    side=trade.side,
                    marker_kind="entry",
                )
            )
            exits.append(
                TradeMarker(
                    ts=trade.exit_ts,
                    price=trade.exit_price,
                    trade_seq=trade.seq,
                    side=trade.side,
                    marker_kind="exit",
                )
            )
        return tuple(entries), tuple(exits)


__all__ = [
    "Candle",
    "CandleCollector",
    "ChartDataBuilder",
    "MarkerKind",
    "TradeMarker",
    "TrailingStopCollector",
    "TrailingStopPoint",
]
