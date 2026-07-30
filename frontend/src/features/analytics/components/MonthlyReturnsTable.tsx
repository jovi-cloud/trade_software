import { useMemo, useState } from 'react'
import { ArrowDown, ArrowUp } from 'lucide-react'

import { formatCurrency, formatPercent } from '@/lib/format'

import type { MonthlyReturn } from '../types'

type SortKey = 'year' | 'month' | 'return_pct' | 'pnl' | 'trading_days'
type SortDir = 'asc' | 'desc'

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

interface MonthlyReturnsTableProps {
  rows: MonthlyReturn[]
}

function SortHeader({
  label,
  active,
  direction,
  onClick,
}: {
  label: string
  active: boolean
  direction: SortDir
  onClick: () => void
}) {
  return (
    <button
      type="button"
      className="inline-flex items-center gap-1 font-medium hover:text-foreground"
      onClick={onClick}
    >
      {label}
      {active &&
        (direction === 'asc' ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}
    </button>
  )
}

export function MonthlyReturnsTable({ rows }: MonthlyReturnsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>('year')
  const [sortDir, setSortDir] = useState<SortDir>('desc')

  const sorted = useMemo(() => {
    const copy = [...rows]
    copy.sort((a, b) => {
      let cmp = 0
      switch (sortKey) {
        case 'year':
          cmp = a.year - b.year || a.month - b.month
          break
        case 'month':
          cmp = a.month - b.month || a.year - b.year
          break
        case 'return_pct':
          cmp = a.return_pct - b.return_pct
          break
        case 'pnl':
          cmp = a.pnl - b.pnl
          break
        case 'trading_days':
          cmp = a.trading_days - b.trading_days
          break
      }
      return sortDir === 'asc' ? cmp : -cmp
    })
    return copy
  }, [rows, sortKey, sortDir])

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((current) => (current === 'asc' ? 'desc' : 'asc'))
      return
    }
    setSortKey(key)
    setSortDir(key === 'year' ? 'desc' : 'desc')
  }

  if (rows.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No monthly returns — need at least one trading day.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-sm">
        <thead className="bg-muted/40 text-xs text-muted-foreground">
          <tr>
            <th className="px-3 py-2">
              <SortHeader
                label="Year"
                active={sortKey === 'year'}
                direction={sortDir}
                onClick={() => toggleSort('year')}
              />
            </th>
            <th className="px-3 py-2">
              <SortHeader
                label="Month"
                active={sortKey === 'month'}
                direction={sortDir}
                onClick={() => toggleSort('month')}
              />
            </th>
            <th className="px-3 py-2">
              <SortHeader
                label="Return"
                active={sortKey === 'return_pct'}
                direction={sortDir}
                onClick={() => toggleSort('return_pct')}
              />
            </th>
            <th className="px-3 py-2">
              <SortHeader
                label="PnL"
                active={sortKey === 'pnl'}
                direction={sortDir}
                onClick={() => toggleSort('pnl')}
              />
            </th>
            <th className="px-3 py-2 font-medium">Start equity</th>
            <th className="px-3 py-2 font-medium">End equity</th>
            <th className="px-3 py-2">
              <SortHeader
                label="Days"
                active={sortKey === 'trading_days'}
                direction={sortDir}
                onClick={() => toggleSort('trading_days')}
              />
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={`${row.year}-${row.month}`} className="border-t border-border">
              <td className="px-3 py-2">{row.year}</td>
              <td className="px-3 py-2">{MONTH_NAMES[row.month - 1] ?? row.month}</td>
              <td
                className={`px-3 py-2 font-medium tabular-nums ${
                  row.return_pct >= 0 ? 'text-emerald-600' : 'text-red-600'
                }`}
              >
                {formatPercent(row.return_pct)}
              </td>
              <td
                className={`px-3 py-2 tabular-nums ${
                  row.pnl >= 0 ? 'text-emerald-600' : 'text-red-600'
                }`}
              >
                {formatCurrency(row.pnl)}
              </td>
              <td className="px-3 py-2 tabular-nums">{formatCurrency(row.start_equity)}</td>
              <td className="px-3 py-2 tabular-nums">{formatCurrency(row.end_equity)}</td>
              <td className="px-3 py-2 tabular-nums">{row.trading_days}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
