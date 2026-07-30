import { formatMetricValue } from '@/features/analytics/formatMetric'

import type { ComparisonReport, MetricComparisonRow } from './types'

function escapeCsv(value: string): string {
  if (value.includes(',') || value.includes('"') || value.includes('\n')) {
    return `"${value.replaceAll('"', '""')}"`
  }
  return value
}

export function comparisonToCsv(report: ComparisonReport): string {
  const headers = [
    'Metric',
  ]
  for (const run of report.runs) {
    headers.push(`Run ${run.label}`)
  }
  headers.push('Best', 'Spread', 'Spread %')

  const lines = [headers.join(',')]
  for (const row of report.metric_rows) {
    const cells = [
      escapeCsv(row.label),
      ...row.values.map((value) =>
        escapeCsv(formatMetricValue(value, row.format, row.precision)),
      ),
      row.best_run_index !== null ? report.runs[row.best_run_index]?.label ?? '' : '',
      row.spread !== null ? String(row.spread) : '',
      row.spread_pct !== null ? String(row.spread_pct) : '',
    ]
    lines.push(cells.join(','))
  }
  return lines.join('\n')
}

export function comparisonToJson(report: ComparisonReport): string {
  return JSON.stringify(report, null, 2)
}

export function downloadTextFile(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export function filterMetricRows(
  rows: MetricComparisonRow[],
  options: { category?: string; query?: string; headlineOnly?: boolean },
): MetricComparisonRow[] {
  const query = options.query?.trim().toLowerCase() ?? ''
  return rows.filter((row) => {
    if (options.category && row.category !== options.category) return false
    if (options.headlineOnly && !row.key.includes('headline')) {
      const headlineKeys = new Set([
        'net_profit',
        'total_return_pct',
        'cagr_pct',
        'profit_factor',
        'expectancy',
        'max_drawdown_pct',
        'exposure_pct',
        'sharpe_ratio',
        'sortino_ratio',
        'calmar_ratio',
        'total_trades',
        'win_rate_pct',
      ])
      if (!headlineKeys.has(row.key)) return false
    }
    if (!query) return true
    return (
      row.label.toLowerCase().includes(query) ||
      row.key.toLowerCase().includes(query) ||
      row.description.toLowerCase().includes(query)
    )
  })
}
