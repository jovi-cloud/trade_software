import type { SeriesMarkerBar, Time, UTCTimestamp } from 'lightweight-charts'

import type { components } from '@/types/api'

type Candle = components['schemas']['CandleRead']
type TradeMarker = components['schemas']['TradeMarkerRead']
type TrailingStopPoint = components['schemas']['TrailingStopPointRead']

/** Bar timestamps are int64 UTC epoch milliseconds; LWC expects seconds. */
export function toChartTime(ts: number): UTCTimestamp {
  return (ts / 1000) as UTCTimestamp
}

export function candlesToSeriesData(candles: Candle[]) {
  return candles.map((candle) => ({
    time: toChartTime(candle.ts),
    open: candle.open,
    high: candle.high,
    low: candle.low,
    close: candle.close,
  }))
}

const MARKER_COLORS = {
  longEntry: '#22c55e',
  longExit: '#3b82f6',
  shortEntry: '#ef4444',
  shortExit: '#f97316',
} as const

function markerStyle(
  marker: TradeMarker,
): Pick<SeriesMarkerBar<Time>, 'position' | 'shape' | 'color'> {
  if (marker.marker_kind === 'entry') {
    if (marker.side === 'long') {
      return { position: 'belowBar', shape: 'arrowUp', color: MARKER_COLORS.longEntry }
    }
    return { position: 'aboveBar', shape: 'arrowDown', color: MARKER_COLORS.shortEntry }
  }

  if (marker.side === 'long') {
    return { position: 'aboveBar', shape: 'circle', color: MARKER_COLORS.longExit }
  }
  return { position: 'belowBar', shape: 'circle', color: MARKER_COLORS.shortExit }
}

export function tradeMarkersToSeriesMarkers(
  entryMarkers: TradeMarker[],
  exitMarkers: TradeMarker[],
): SeriesMarkerBar<Time>[] {
  const combined = [...entryMarkers, ...exitMarkers]
  return combined
    .map((marker) => {
      const style = markerStyle(marker)
      return {
        time: toChartTime(marker.ts),
        ...style,
        id: `${marker.marker_kind}-${marker.trade_seq}`,
        text: `#${marker.trade_seq}`,
      }
    })
    .toSorted((left, right) => (left.time as number) - (right.time as number))
}

export function chartTimeToEpochMs(time: Time | undefined): number | null {
  if (time === undefined) return null
  if (typeof time === 'number') return time * 1000
  if (typeof time === 'string') return Number(time) * 1000
  return null
}

/** Build a line series with gaps between separate trades. */
export function trailingStopToSeriesData(
  points: TrailingStopPoint[],
  tradeSeq: number | null,
) {
  const filtered =
    tradeSeq === null ? points : points.filter((point) => point.trade_seq === tradeSeq)
  if (filtered.length === 0) return []

  const grouped = new Map<number, TrailingStopPoint[]>()
  for (const point of filtered) {
    const bucket = grouped.get(point.trade_seq) ?? []
    bucket.push(point)
    grouped.set(point.trade_seq, bucket)
  }

  const data: Array<{ time: UTCTimestamp; value?: number }> = []
  for (const tradePoints of [...grouped.values()].toSorted(
    (left, right) => left[0].ts - right[0].ts,
  )) {
    if (data.length > 0) {
      data.push({ time: toChartTime(tradePoints[0].ts) })
    }
    for (const point of tradePoints) {
      data.push({ time: toChartTime(point.ts), value: point.level })
    }
  }
  return data
}
