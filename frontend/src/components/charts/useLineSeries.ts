import { LineSeries, type IChartApi, type ISeriesApi } from 'lightweight-charts'
import type { RefObject } from 'react'
import { useEffect, useRef } from 'react'

import type { Theme } from '@/hooks/useTheme'

export function useLineSeries(chartRef: RefObject<IChartApi | null>, theme: Theme) {
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null)

  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return

    const isDark = theme === 'dark'
    const series = chart.addSeries(LineSeries, {
      color: isDark ? '#60a5fa' : '#2563eb',
      lineWidth: 2,
    })
    seriesRef.current = series

    return () => {
      seriesRef.current = null
    }
  }, [chartRef, theme])

  return seriesRef
}
