import { useEffect, useMemo, useState } from 'react'
import type { MouseEventParams } from 'lightweight-charts'

import { ChartContainer } from '@/components/charts/ChartContainer'
import { chartTimeToEpochMs, toChartTime } from '@/components/charts/seriesHelpers'
import { useLightweightChart } from '@/components/charts/useLightweightChart'
import { useLineSeries } from '@/components/charts/useLineSeries'
import { useTheme } from '@/hooks/useTheme'
import { formatCurrency, formatTimestamp } from '@/lib/format'

import type { EquityCurvePoint } from '../types'

interface AnalyticsEquityChartProps {
  equityCurve: EquityCurvePoint[]
  downsampled?: boolean
}

interface TooltipState {
  x: number
  y: number
  equity: string
  realised: string
  timestamp: string
}

export function AnalyticsEquityChart({
  equityCurve,
  downsampled = false,
}: AnalyticsEquityChartProps) {
  const { theme } = useTheme()
  const { containerRef, chartRef } = useLightweightChart(theme)
  const seriesRef = useLineSeries(chartRef, theme)
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)

  const seriesData = useMemo(
    () =>
      equityCurve.map((point) => ({
        time: toChartTime(point.ts),
        value: point.equity,
      })),
    [equityCurve],
  )

  const pointByTime = useMemo(() => {
    const map = new Map<number, EquityCurvePoint>()
    for (const point of equityCurve) {
      map.set(toChartTime(point.ts) as number, point)
    }
    return map
  }, [equityCurve])

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
        equity: formatCurrency(point.equity),
        realised: formatCurrency(point.realised),
        timestamp: formatTimestamp(point.ts),
      })
    }

    chart.subscribeCrosshairMove(handleCrosshair)
    return () => chart.unsubscribeCrosshairMove(handleCrosshair)
  }, [chartRef, pointByTime])

  if (equityCurve.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        No equity data — the curve appears once bars are processed.
      </p>
    )
  }

  return (
    <div className="space-y-2">
      {downsampled && (
        <p className="text-xs text-muted-foreground">
          Curve downsampled for display. Headline metrics use the full series.
        </p>
      )}
      <ChartContainer height={420}>
        <div ref={containerRef} className="absolute inset-0" />
        {tooltip && (
          <div
            className="pointer-events-none absolute z-10 rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md"
            style={{ left: tooltip.x + 12, top: tooltip.y + 12 }}
          >
            <p className="font-medium">{tooltip.equity}</p>
            <p className="text-muted-foreground">Realised: {tooltip.realised}</p>
            <p className="text-muted-foreground">{tooltip.timestamp}</p>
          </div>
        )}
      </ChartContainer>
    </div>
  )
}
