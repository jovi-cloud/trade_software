import {
  CandlestickSeries,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type SeriesMarker,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import type { RefObject } from 'react'
import { useEffect, useRef } from 'react'

import type { Theme } from '@/hooks/useTheme'

function chartOptions(theme: Theme) {
  const isDark = theme === 'dark'
  return {
    layout: {
      background: { color: 'transparent' },
      textColor: isDark ? '#d4d4d8' : '#3f3f46',
    },
    grid: {
      vertLines: { color: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' },
      horzLines: { color: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)' },
    },
    rightPriceScale: {
      borderColor: isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)',
    },
    timeScale: {
      borderColor: isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.12)',
      timeVisible: true,
      secondsVisible: false,
    },
    crosshair: {
      mode: 0 as const,
    },
    handleScroll: true,
    handleScale: true,
  }
}

export interface LightweightChartHandle {
  chart: IChartApi
  container: HTMLDivElement
}

export function useLightweightChart(theme: Theme) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const chart = createChart(container, {
      ...chartOptions(theme),
      width: container.clientWidth,
      height: container.clientHeight,
    })
    chartRef.current = chart

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      const { width, height } = entry.contentRect
      chart.applyOptions({ width, height })
    })
    observer.observe(container)

    return () => {
      observer.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [theme])

  return { containerRef, chartRef }
}

export function useCandlestickSeries(
  chartRef: RefObject<IChartApi | null>,
  theme: Theme,
) {
  const seriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const markersRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)

  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return

    const isDark = theme === 'dark'
    const series = chart.addSeries(CandlestickSeries, {
      upColor: isDark ? '#22c55e' : '#16a34a',
      downColor: isDark ? '#ef4444' : '#dc2626',
      borderVisible: false,
      wickUpColor: isDark ? '#22c55e' : '#16a34a',
      wickDownColor: isDark ? '#ef4444' : '#dc2626',
    })
    seriesRef.current = series
    markersRef.current = createSeriesMarkers(series)

    return () => {
      markersRef.current = null
      seriesRef.current = null
    }
  }, [chartRef, theme])

  return { seriesRef, markersRef }
}

export type { SeriesMarker, Time, UTCTimestamp }
