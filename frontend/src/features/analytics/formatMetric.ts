import {
  formatCurrency,
  formatDuration,
  formatInteger,
  formatNumber,
  formatPercent,
} from '@/lib/format'

import type { MetricFormat } from './types'

const PLACEHOLDER = '--'

/** Format a metric value using the catalog's display format and precision. */
export function formatMetricValue(
  value: number | null | undefined,
  format: MetricFormat,
  precision = 2,
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return PLACEHOLDER

  switch (format) {
    case 'currency':
      return formatCurrency(value)
    case 'percent':
      return formatPercent(value, precision)
    case 'ratio':
      return value.toFixed(precision)
    case 'integer':
      return formatInteger(value)
    case 'duration':
      return formatDuration(value)
    case 'number':
      return formatNumber(value, precision)
    default:
      return formatNumber(value, precision)
  }
}

/** Colour class for a metric where higher is better (or lower for drawdown-type). */
export function metricValueTone(
  value: number | null | undefined,
  higherIsBetter: boolean | null,
): string {
  if (value === null || value === undefined || higherIsBetter === null) return ''
  if (value === 0) return 'text-muted-foreground'
  const positive = value > 0
  const good = higherIsBetter ? positive : !positive
  return good ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
}
