import { useEffect, useMemo, useState } from 'react'
import type { MouseEventParams } from 'lightweight-charts'

import { ChartContainer } from '@/components/charts/ChartContainer'
import { chartTimeToEpochMs, toChartTime } from '@/components/charts/seriesHelpers'
import { useLightweightChart } from '@/components/charts/useLightweightChart'
import { useLineSeries } from '@/components/charts/useLineSeries'
import { useTheme } from '@/hooks/useTheme'
import { formatCurrency, formatInteger, formatTimestamp } from '@/lib/format'

import type { ExecutionResult } from '../types'

interface EquityChartProps {
  equityHistory: ExecutionResult['equity_history']
}

interface TooltipState {
  x: number
  y: number
  tradeNumber: string
  equity: string
  timestamp: string
}

export function EquityChart({ equityHistory }: EquityChartProps) {
  const { theme } = useTheme()
  const { containerRef, chartRef } = useLightweightChart(theme)
  const seriesRef = useLineSeries(chartRef, theme)
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)

  const seriesData = useMemo(
    () =>
      equityHistory.map((point) => ({
        time: toChartTime(point.timestamp),
        value: point.equity,
      })),
    [equityHistory],
  )

  const pointByTime = useMemo(() => {
    const map = new Map<number, ExecutionResult['equity_history'][number]>()
    for (const point of equityHistory) {
      map.set(toChartTime(point.timestamp) as number, point)
    }
    return map
  }, [equityHistory])

  useEffect(() => {
    const series = seriesRef.current
    if (!series) return
    series.setData(seriesData)
    chartRef.current?.timeScale().fitContent()
  }, [chartRef, seriesData, seriesRef])

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

      const point = pointByTime.get(Math.floor(epochMs / 1000))
      if (!point) {
        setTooltip(null)
        return
      }

      setTooltip({
        x: param.point.x,
        y: param.point.y,
        tradeNumber: formatInteger(point.trade_number),
        equity: formatCurrency(point.equity),
        timestamp: formatTimestamp(point.timestamp),
      })
    }

    chart.subscribeCrosshairMove(handleCrosshair)

    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshair)
    }
  }, [chartRef, pointByTime])

  if (equityHistory.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        No closed trades — equity curve will appear after the first round trip.
      </p>
    )
  }

  return (
    <ChartContainer height={420}>
      <div ref={containerRef} className="absolute inset-0" />
      {tooltip && (
        <div
          className="pointer-events-none absolute z-10 rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md"
          style={{ left: tooltip.x + 12, top: tooltip.y + 12 }}
        >
          <p>Trade {tooltip.tradeNumber}</p>
          <p className="font-medium">{tooltip.equity}</p>
          <p className="text-muted-foreground">{tooltip.timestamp}</p>
        </div>
      )}
    </ChartContainer>
  )
}
