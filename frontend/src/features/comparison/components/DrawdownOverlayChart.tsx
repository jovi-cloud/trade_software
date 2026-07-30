import { LineSeries } from 'lightweight-charts'
import { useEffect, useMemo, useState } from 'react'

import { ChartContainer } from '@/components/charts/ChartContainer'
import { toChartTime } from '@/components/charts/seriesHelpers'
import { useLightweightChart } from '@/components/charts/useLightweightChart'
import { useTheme } from '@/hooks/useTheme'
import { Button } from '@/components/ui/button'
import { formatTimestamp } from '@/lib/format'

import type { ComparisonReport } from '../types'
import { RUN_COLORS } from '../types'

interface DrawdownOverlayChartProps {
  overlays: ComparisonReport['drawdown_overlays']
}

export function DrawdownOverlayChart({ overlays }: DrawdownOverlayChartProps) {
  const { theme } = useTheme()
  const { containerRef, chartRef } = useLightweightChart(theme)
  const [hidden, setHidden] = useState<Set<string>>(new Set())

  const visible = useMemo(
    () => overlays.filter((overlay) => !hidden.has(overlay.run_id)),
    [overlays, hidden],
  )

  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return

    const seriesList = visible.map((overlay, index) => {
      const color = RUN_COLORS[index % RUN_COLORS.length]
      const series = chart.addSeries(LineSeries, { color, lineWidth: 2, title: overlay.run_label })
      series.setData(
        overlay.points.map((point) => ({
          time: toChartTime(point.ts),
          value: -Math.abs(point.depth_pct),
        })),
      )
      return series
    })

    chart.timeScale().fitContent()

    return () => {
      for (const series of seriesList) {
        chart.removeSeries(series)
      }
    }
  }, [chartRef, visible])

  if (overlays.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        No drawdown curves to overlay.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {overlays.map((overlay, index) => {
          const active = !hidden.has(overlay.run_id)
          return (
            <Button
              key={overlay.run_id}
              type="button"
              size="sm"
              variant={active ? 'default' : 'outline'}
              onClick={() =>
                setHidden((current) => {
                  const next = new Set(current)
                  if (next.has(overlay.run_id)) next.delete(overlay.run_id)
                  else next.add(overlay.run_id)
                  return next
                })
              }
            >
              <span
                className="mr-2 inline-block size-2 rounded-full"
                style={{ backgroundColor: RUN_COLORS[index % RUN_COLORS.length] }}
              />
              Run {overlay.run_label}
            </Button>
          )
        })}
      </div>
      <div className="grid gap-2 text-xs text-muted-foreground md:grid-cols-2">
        {overlays.map((overlay) => (
          <div key={overlay.run_id} className="rounded-md border border-border p-2">
            <p className="font-medium text-foreground">Run {overlay.run_label}</p>
            <p>
              Trough:{' '}
              {overlay.max_drawdown_trough_ts
                ? formatTimestamp(overlay.max_drawdown_trough_ts)
                : '—'}
            </p>
            <p>
              Recovery:{' '}
              {overlay.max_drawdown_recovery_ts
                ? formatTimestamp(overlay.max_drawdown_recovery_ts)
                : 'Not recovered'}
            </p>
          </div>
        ))}
      </div>
      <ChartContainer height={360}>
        <div ref={containerRef} className="absolute inset-0" />
      </ChartContainer>
      <p className="text-xs text-muted-foreground">Y-axis shows drawdown depth in percent.</p>
    </div>
  )
}
