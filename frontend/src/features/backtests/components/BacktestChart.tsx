import { useEffect, useMemo, useState } from 'react'
import type { MouseEventParams } from 'lightweight-charts'

import { ChartContainer } from '@/components/charts/ChartContainer'
import { candlesToSeriesData, chartTimeToEpochMs } from '@/components/charts/seriesHelpers'
import { useCandlestickSeries, useLightweightChart } from '@/components/charts/useLightweightChart'
import { useTheme } from '@/hooks/useTheme'
import { formatNumber, formatTimestamp } from '@/lib/format'

import type { ExecutionResult } from '../types'
import { buildMarkerTradeLookup, buildTradeMarkers } from './TradeMarkers'
import { TradeDetailsPanel } from './TradeDetailsPanel'

interface BacktestChartProps {
  result: ExecutionResult
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

export function BacktestChart({ result }: BacktestChartProps) {
  const { theme } = useTheme()
  const { containerRef, chartRef } = useLightweightChart(theme)
  const { seriesRef, markersRef } = useCandlestickSeries(chartRef, theme)
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
  const candleByTime = useMemo(() => {
    const map = new Map<number, ExecutionResult['candles'][number]>()
    for (const candle of result.candles) {
      map.set(Math.floor(candle.ts / 1000), candle)
    }
    return map
  }, [result.candles])

  const activeTradeSeq = localTradeSeq
  const selectedTrade =
    activeTradeSeq === null
      ? null
      : (result.trades.find((trade) => trade.seq === activeTradeSeq) ?? null)

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

      const candle = candleByTime.get(Math.floor(epochMs / 1000))
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
      const tradeSeq = markerLookup.get(Math.floor(epochMs / 1000))
      if (tradeSeq === undefined) return
      setLocalTradeSeq(tradeSeq)
    }

    chart.subscribeCrosshairMove(handleCrosshair)
    chart.subscribeClick(handleClick)

    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshair)
      chart.unsubscribeClick(handleClick)
    }
  }, [candleByTime, chartRef, markerLookup])

  return (
    <div className="space-y-4">
      <ChartContainer height={420}>
        <div ref={containerRef} className="absolute inset-0" />
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
