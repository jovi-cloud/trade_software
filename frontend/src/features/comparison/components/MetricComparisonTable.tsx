import { Info } from 'lucide-react'
import { useMemo, useState } from 'react'

import { formatMetricValue } from '@/features/analytics/formatMetric'
import { Input } from '@/components/ui/input'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

import type { ComparisonReport, MetricComparisonRow } from '../types'
import { filterMetricRows } from '../export'

interface MetricComparisonTableProps {
  report: ComparisonReport
  category?: string
  headlineOnly?: boolean
}

function cellTone(
  row: MetricComparisonRow,
  runIndex: number,
): string {
  if (row.higher_is_better === null || row.values[runIndex] === null) return ''
  if (row.is_tie) return 'bg-muted/40'
  if (row.best_run_index === runIndex) return 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
  if (row.worst_run_index === runIndex) return 'bg-red-500/10 text-red-700 dark:text-red-400'
  return ''
}

export function MetricComparisonTable({
  report,
  category,
  headlineOnly = false,
}: MetricComparisonTableProps) {
  const [query, setQuery] = useState('')

  const rows = useMemo(
    () => filterMetricRows(report.metric_rows, { category, query, headlineOnly }),
    [report.metric_rows, category, query, headlineOnly],
  )

  return (
    <div className="space-y-3">
      <Input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search metrics…"
        className="max-w-sm"
        aria-label="Search metrics"
      />
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="bg-muted/40 text-xs text-muted-foreground">
            <tr>
              <th className="sticky left-0 z-10 bg-muted/95 px-3 py-2 font-medium backdrop-blur">
                Metric
              </th>
              {report.runs.map((run) => (
                <th key={run.run_id} className="px-3 py-2 font-medium">
                  Run {run.label}
                </th>
              ))}
              <th className="px-3 py-2 font-medium">Best</th>
              <th className="px-3 py-2 font-medium">Spread</th>
              <th className="px-3 py-2 font-medium">Spread %</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} className="border-t border-border">
                <td className="sticky left-0 z-10 bg-background px-3 py-2">
                  <div className="flex items-center gap-1.5">
                    <span className="font-medium">{row.label}</span>
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <button
                            type="button"
                            className="text-muted-foreground hover:text-foreground"
                            aria-label={`About ${row.label}`}
                          >
                            <Info className="size-3.5" />
                          </button>
                        </TooltipTrigger>
                        <TooltipContent>{row.description}</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  </div>
                </td>
                {row.values.map((value, index) => (
                  <td
                    key={`${row.key}-${index}`}
                    className={cn('px-3 py-2 tabular-nums', cellTone(row, index))}
                  >
                    {formatMetricValue(value, row.format, row.precision)}
                  </td>
                ))}
                <td className="px-3 py-2 tabular-nums">
                  {row.best_run_index !== null
                    ? `Run ${report.runs[row.best_run_index]?.label ?? '—'}`
                    : row.is_tie
                      ? 'Tie'
                      : '—'}
                </td>
                <td className="px-3 py-2 tabular-nums">
                  {row.spread !== null ? formatMetricValue(row.spread, row.format, row.precision) : '—'}
                </td>
                <td className="px-3 py-2 tabular-nums">
                  {row.spread_pct !== null ? `${row.spread_pct.toFixed(2)}%` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
