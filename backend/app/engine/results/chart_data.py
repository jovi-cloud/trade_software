"""Chart series derived from replayed bars and completed trades.

Pure functions only: no I/O, no metric recomputation. Markers are positioned
from the same trade records the metrics engine already consumed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from app.domain.enums import PositionSide
from app.engine.bars import bar_from_row
from app.engine.execution.trade import Trade

MarkerKind = Literal["entry", "exit"]


@dataclass(frozen=True)
class Candle:
    """One OHLCV bar for the price chart."""

    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class TradeMarker:
    """Entry or exit marker anchored to one trade."""

    ts: int
    price: float
    trade_seq: int
    side: PositionSide
    marker_kind: MarkerKind


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


__all__ = ["Candle", "ChartDataBuilder", "MarkerKind", "TradeMarker"]
