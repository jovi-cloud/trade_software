import { LineSeries, type ISeriesApi } from 'lightweight-charts'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { MouseEventParams } from 'lightweight-charts'

import { ChartContainer } from '@/components/charts/ChartContainer'
import {
  candlesToSeriesData,
  chartTimeToEpochMs,
  trailingStopToSeriesData,
} from '@/components/charts/seriesHelpers'
import { useCandlestickSeries, useLightweightChart } from '@/components/charts/useLightweightChart'
import { useTheme } from '@/hooks/useTheme'
import { formatNumber, formatTimestamp } from '@/lib/format'

import type { ExecutionResult } from '../types'
import { buildMarkerTradeLookup, buildTradeMarkers } from './TradeMarkers'
import { TradeDetailsPanel } from './TradeDetailsPanel'

interface BacktestChartProps {
  result: ExecutionResult
  onBarSelect?: (barIndex: number) => void
  selectedBarIndex?: number | null
}

interface TooltipState {
  x: number
  y: number
  time: string
  open: string
  high: string
  low: string
  close: string
}

export function BacktestChart({ result, onBarSelect, selectedBarIndex }: BacktestChartProps) {
  const { theme } = useTheme()
  const { containerRef, chartRef } = useLightweightChart(theme)
  const { seriesRef, markersRef } = useCandlestickSeries(chartRef, theme)
  const trailingSeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const [localTradeSeq, setLocalTradeSeq] = useState<number | null>(null)

  const candleData = useMemo(() => candlesToSeriesData(result.candles), [result.candles])
  const markers = useMemo(
    () => buildTradeMarkers(result.entry_markers, result.exit_markers),
    [result.entry_markers, result.exit_markers],
  )
  const markerLookup = useMemo(
    () => buildMarkerTradeLookup(result.entry_markers, result.exit_markers),
    [result.entry_markers, result.exit_markers],
  )
  const trailingStopData = useMemo(
    () =>
      trailingStopToSeriesData(result.trailing_stop_points ?? [], localTradeSeq ?? null),
    [localTradeSeq, result.trailing_stop_points],
  )
  const candleIndexByTime = useMemo(() => {
    const map = new Map<number, number>()
    result.candles.forEach((candle, index) => {
      map.set(Math.floor(candle.ts / 1000), index)
    })
    return map
  }, [result.candles])

  const activeTradeSeq = localTradeSeq
  const selectedTrade =
    activeTradeSeq === null
      ? null
      : (result.trades.find((trade) => trade.seq === activeTradeSeq) ?? null)

  useEffect(() => {
    const chart = chartRef.current
    if (!chart || trailingSeriesRef.current) return

    const isDark = theme === 'dark'
    const series = chart.addSeries(LineSeries, {
      color: isDark ? '#fbbf24' : '#d97706',
      lineWidth: 2,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    })
    trailingSeriesRef.current = series

    return () => {
      trailingSeriesRef.current = null
    }
  }, [chartRef, theme])

  useEffect(() => {
    const series = seriesRef.current
    if (!series) return
    series.setData(candleData)
    chartRef.current?.timeScale().fitContent()
  }, [candleData, chartRef, seriesRef])

  useEffect(() => {
    markersRef.current?.setMarkers(markers)
  }, [markers, markersRef])

  useEffect(() => {
    const series = trailingSeriesRef.current
    if (!series) return
    series.setData(trailingStopData)
  }, [trailingStopData])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return

    const handleCrosshair = (param: MouseEventParams) => {
      if (!param.point || param.time === undefined) {
        setTooltip(null)
        return
      }

      const epochMs = chartTimeToEpochMs(param.time)
      if (epochMs === null) {
        setTooltip(null)
        return
      }

      const candle = result.candles[candleIndexByTime.get(Math.floor(epochMs / 1000)) ?? -1]
      if (!candle) {
        setTooltip(null)
        return
      }

      setTooltip({
        x: param.point.x,
        y: param.point.y,
        time: formatTimestamp(candle.ts),
        open: formatNumber(candle.open, 4),
        high: formatNumber(candle.high, 4),
        low: formatNumber(candle.low, 4),
        close: formatNumber(candle.close, 4),
      })
    }

    const handleClick = (param: MouseEventParams) => {
      if (param.time === undefined) return
      const epochMs = chartTimeToEpochMs(param.time)
      if (epochMs === null) return
      const barIndex = candleIndexByTime.get(Math.floor(epochMs / 1000))
      if (barIndex !== undefined) {
        onBarSelect?.(barIndex)
      }
      const tradeSeq = markerLookup.get(Math.floor(epochMs / 1000))
      if (tradeSeq !== undefined) {
        setLocalTradeSeq(tradeSeq)
      }
    }

    chart.subscribeCrosshairMove(handleCrosshair)
    chart.subscribeClick(handleClick)

    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshair)
      chart.unsubscribeClick(handleClick)
    }
  }, [candleIndexByTime, chartRef, markerLookup, onBarSelect, result.candles])

  return (
    <div className="space-y-4">
      <ChartContainer height={420}>
        <div ref={containerRef} className="absolute inset-0" />
        {selectedBarIndex !== null && selectedBarIndex !== undefined && (
          <div className="absolute left-3 top-3 rounded-md border border-primary/40 bg-background/90 px-2 py-1 text-xs">
            Inspecting bar {selectedBarIndex + 1}
          </div>
        )}
        {(result.trailing_stop_points?.length ?? 0) > 0 && (
          <div className="absolute right-3 top-3 rounded-md border border-amber-500/40 bg-background/90 px-2 py-1 text-xs text-amber-700 dark:text-amber-300">
            Dashed line: trailing stop
          </div>
        )}
        {tooltip && (
          <div
            className="pointer-events-none absolute z-10 rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md"
            style={{ left: tooltip.x + 12, top: tooltip.y + 12 }}
          >
            <p className="font-medium">{tooltip.time}</p>
            <p>O {tooltip.open}</p>
            <p>H {tooltip.high}</p>
            <p>L {tooltip.low}</p>
            <p>C {tooltip.close}</p>
          </div>
        )}
      </ChartContainer>

      <TradeDetailsPanel
        trade={selectedTrade}
        onClose={() => {
          setLocalTradeSeq(null)
        }}
      />
    </div>
  )
}
