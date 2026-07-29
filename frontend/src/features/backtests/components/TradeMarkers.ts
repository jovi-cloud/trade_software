import type { SeriesMarker, Time } from 'lightweight-charts'

import type { components } from '@/types/api'

import { toChartTime, tradeMarkersToSeriesMarkers } from '@/components/charts/seriesHelpers'

type TradeMarker = components['schemas']['TradeMarkerRead']

export function buildTradeMarkers(
  entryMarkers: TradeMarker[],
  exitMarkers: TradeMarker[],
): SeriesMarker<Time>[] {
  return tradeMarkersToSeriesMarkers(entryMarkers, exitMarkers)
}

/** Map chart time (seconds) to trade sequence for marker click handling. */
export function buildMarkerTradeLookup(
  entryMarkers: TradeMarker[],
  exitMarkers: TradeMarker[],
): Map<number, number> {
  const lookup = new Map<number, number>()
  for (const marker of [...entryMarkers, ...exitMarkers]) {
    lookup.set(toChartTime(marker.ts) as number, marker.trade_seq)
  }
  return lookup
}

export function parseMarkerId(markerId: string | undefined): number | null {
  if (!markerId) return null
  const parts = markerId.split('-')
  const seq = Number(parts[1])
  return Number.isFinite(seq) ? seq : null
}
