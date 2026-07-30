import { useMemo, useState } from 'react'
import { ArrowDown, ArrowUp } from 'lucide-react'

import { formatPercent } from '@/lib/format'

import type { ComparisonReport } from '../types'
import { RUN_COLORS } from '../types'

const MONTH_NAMES = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]

interface MonthlyComparisonTableProps {
  overlays: ComparisonReport['monthly_returns_overlays']
}

type SortKey = 'period' | 'return_pct'
type SortDir = 'asc' | 'desc'

export function MonthlyComparisonTable({ overlays }: MonthlyComparisonTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('period')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const rows = useMemo(() => {
    const map = new Map<string, { year: number; month: number; values: (number | null)[] }>()
    overlays.forEach((overlay, runIndex) => {
      for (const raw of overlay.returns) {
        const item = raw as { year: number; month: number; return_pct: number }
        const key = `${item.year}-${item.month}`
        const existing = map.get(key) ?? {
          year: item.year,
          month: item.month,
          values: Array.from({ length: overlays.length }, () => null),
        }
        existing.values[runIndex] = item.return_pct
        map.set(key, existing)
      }
    })

    const list = [...map.values()]
    list.sort((a, b) => {
      const cmp =
        sortKey === 'period'
          ? a.year - b.year || a.month - b.month
          : (a.values[0] ?? 0) - (b.values[0] ?? 0)
      return sortDir === 'asc' ? cmp : -cmp
    })
    return list
  }, [overlays, sortKey, sortDir])

  if (overlays.length === 0 || rows.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No monthly returns available for these runs.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-sm">
        <thead className="bg-muted/40 text-xs text-muted-foreground">
          <tr>
            <th className="px-3 py-2">
              <button
                type="button"
                className="inline-flex items-center gap-1 font-medium"
                onClick={() => {
                  setSortKey('period')
                  setSortDir((current) => (current === 'asc' ? 'desc' : 'asc'))
                }}
              >
                Period
                {sortKey === 'period' &&
                  (sortDir === 'asc' ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}
              </button>
            </th>
            {overlays.map((overlay, index) => (
              <th key={overlay.run_id} className="px-3 py-2 font-medium">
                <span
                  className="mr-2 inline-block size-2 rounded-full align-middle"
                  style={{ backgroundColor: RUN_COLORS[index % RUN_COLORS.length] }}
                />
                Run {overlay.run_label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.year}-${row.month}`} className="border-t border-border">
              <td className="px-3 py-2 font-medium">
                {MONTH_NAMES[row.month - 1]} {row.year}
              </td>
              {row.values.map((value, index) => (
                <td
                  key={`${row.year}-${row.month}-${index}`}
                  className={`px-3 py-2 tabular-nums ${
                    value !== null && value >= 0 ? 'text-emerald-600' : 'text-red-600'
                  }`}
                >
                  {value !== null ? formatPercent(value) : '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
