import { useEffect, useMemo, useState } from 'react'
import type { MouseEventParams } from 'lightweight-charts'

import { ChartContainer } from '@/components/charts/ChartContainer'
import { chartTimeToEpochMs, toChartTime } from '@/components/charts/seriesHelpers'
import { useLightweightChart } from '@/components/charts/useLightweightChart'
import { useLineSeries } from '@/components/charts/useLineSeries'
import { useTheme } from '@/hooks/useTheme'
import { formatCurrency, formatPercent, formatTimestamp } from '@/lib/format'

import type { DrawdownPoint } from '../types'

interface DrawdownChartProps {
  drawdownCurve: DrawdownPoint[]
  downsampled?: boolean
  maxDrawdownStartTs?: number | null
  maxDrawdownTroughTs?: number | null
  maxDrawdownRecoveryTs?: number | null
}

interface TooltipState {
  x: number
  y: number
  depth: string
  depthPct: string
  timestamp: string
}

export function DrawdownChart({
  drawdownCurve,
  downsampled = false,
  maxDrawdownStartTs,
  maxDrawdownTroughTs,
  maxDrawdownRecoveryTs,
}: DrawdownChartProps) {
  const { theme } = useTheme()
  const { containerRef, chartRef } = useLightweightChart(theme)
  const seriesRef = useLineSeries(chartRef, theme)
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)

  const isDark = theme === 'dark'

  const seriesData = useMemo(
    () =>
      drawdownCurve.map((point) => ({
        time: toChartTime(point.ts),
        value: -Math.abs(point.depth_pct),
      })),
    [drawdownCurve],
  )

  const pointByTime = useMemo(() => {
    const map = new Map<number, DrawdownPoint>()
    for (const point of drawdownCurve) {
      map.set(toChartTime(point.ts) as number, point)
    }
    return map
  }, [drawdownCurve])

  useEffect(() => {
    const series = seriesRef.current
    if (!series) return
    series.applyOptions({
      color: isDark ? '#f87171' : '#dc2626',
      lineWidth: 2,
    })
    series.setData(seriesData)
    chartRef.current?.timeScale().fitContent()
  }, [chartRef, isDark, seriesData, seriesRef])

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
        depth: formatCurrency(point.depth),
        depthPct: formatPercent(point.depth_pct),
        timestamp: formatTimestamp(point.ts),
      })
    }

    chart.subscribeCrosshairMove(handleCrosshair)
    return () => chart.unsubscribeCrosshairMove(handleCrosshair)
  }, [chartRef, pointByTime])

  if (drawdownCurve.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        No drawdown data available.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {downsampled && (
        <p className="text-xs text-muted-foreground">
          Curve downsampled for display. Maximum drawdown metrics use the full series.
        </p>
      )}
      {(maxDrawdownStartTs || maxDrawdownTroughTs) && (
        <dl className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-3">
          {maxDrawdownStartTs && (
            <div>
              <dt>Peak</dt>
              <dd>{formatTimestamp(maxDrawdownStartTs)}</dd>
            </div>
          )}
          {maxDrawdownTroughTs && (
            <div>
              <dt>Trough</dt>
              <dd>{formatTimestamp(maxDrawdownTroughTs)}</dd>
            </div>
          )}
          {maxDrawdownRecoveryTs && (
            <div>
              <dt>Recovery</dt>
              <dd>{formatTimestamp(maxDrawdownRecoveryTs)}</dd>
            </div>
          )}
          {maxDrawdownRecoveryTs === null && maxDrawdownTroughTs && (
            <div>
              <dt>Recovery</dt>
              <dd>Not recovered</dd>
            </div>
          )}
        </dl>
      )}
      <ChartContainer height={360}>
        <div ref={containerRef} className="absolute inset-0" />
        {tooltip && (
          <div
            className="pointer-events-none absolute z-10 rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-md"
            style={{ left: tooltip.x + 12, top: tooltip.y + 12 }}
          >
            <p className="font-medium">{tooltip.depthPct}</p>
            <p className="text-muted-foreground">{tooltip.depth}</p>
            <p className="text-muted-foreground">{tooltip.timestamp}</p>
          </div>
        )}
      </ChartContainer>
    </div>
  )
}
