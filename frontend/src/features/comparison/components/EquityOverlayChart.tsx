import { LineSeries } from 'lightweight-charts'
import { useEffect, useMemo, useState } from 'react'

import { ChartContainer } from '@/components/charts/ChartContainer'
import { toChartTime } from '@/components/charts/seriesHelpers'
import { useLightweightChart } from '@/components/charts/useLightweightChart'
import { useTheme } from '@/hooks/useTheme'
import { Button } from '@/components/ui/button'

import type { ComparisonReport } from '../types'
import { RUN_COLORS } from '../types'

interface EquityOverlayChartProps {
  overlays: ComparisonReport['equity_overlays']
}

export function EquityOverlayChart({ overlays }: EquityOverlayChartProps) {
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
          value: point.equity,
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
      <p className="py-12 text-center text-sm text-muted-foreground">No equity curves to overlay.</p>
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
      <ChartContainer height={420}>
        <div ref={containerRef} className="absolute inset-0" />
      </ChartContainer>
    </div>
  )
}
