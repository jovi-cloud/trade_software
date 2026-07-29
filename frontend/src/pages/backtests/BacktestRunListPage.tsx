import { Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { PageHeader } from '@/components/common/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { DeleteBacktestRunDialog } from '@/features/backtest-runs/components/DeleteBacktestRunDialog'
import { useBacktestRuns, useDeleteBacktestRun } from '@/features/backtest-runs/queries'
import {
  BACKTEST_RUN_STATUSES,
  type BacktestRunListItem,
  type BacktestRunSortField,
  type BacktestRunStatus,
} from '@/features/backtest-runs/types'
import { formatCurrency, formatDate, formatPercent } from '@/lib/format'
import { getErrorMessage } from '@/lib/apiClient'

const PAGE_SIZE = 20

const SORT_OPTIONS: { value: `${BacktestRunSortField}:${'asc' | 'desc'}`; label: string }[] = [
  { value: 'execution_completed_at:desc', label: 'Newest' },
  { value: 'execution_completed_at:asc', label: 'Oldest' },
  { value: 'net_profit:desc', label: 'Profit (high to low)' },
  { value: 'net_profit:asc', label: 'Profit (low to high)' },
  { value: 'trade_count:desc', label: 'Trade count (high to low)' },
  { value: 'trade_count:asc', label: 'Trade count (low to high)' },
]

type SortValue = (typeof SORT_OPTIONS)[number]['value']

const SKELETON_KEYS = ['sk-1', 'sk-2', 'sk-3', 'sk-4', 'sk-5']

export default function BacktestRunListPage() {
  const [searchInput, setSearchInput] = useState('')
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<BacktestRunStatus | 'all'>('all')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [sortValue, setSortValue] = useState<SortValue>('execution_completed_at:desc')
  const [offset, setOffset] = useState(0)
  const [pendingDelete, setPendingDelete] = useState<BacktestRunListItem | null>(null)

  useEffect(() => {
    const timeout = setTimeout(() => {
      setQ(searchInput.trim())
      setOffset(0)
    }, 300)
    return () => clearTimeout(timeout)
  }, [searchInput])

  const [sort, order] = sortValue.split(':') as [BacktestRunSortField, 'asc' | 'desc']

  const params = useMemo(
    () => ({
      q: q || undefined,
      status: status === 'all' ? undefined : status,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      sort,
      order,
      limit: PAGE_SIZE,
      offset,
    }),
    [q, status, dateFrom, dateTo, sort, order, offset],
  )

  const { data, isLoading, isError, error, refetch } = useBacktestRuns(params)
  const deleteRun = useDeleteBacktestRun()

  const hasFilters =
    q.length > 0 || status !== 'all' || dateFrom.length > 0 || dateTo.length > 0

  return (
    <div>
      <PageHeader
        title="Backtest Runs"
        description="Every completed backtest is saved permanently. Open any run to review its results without re-executing."
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Search experiment, hypothesis, tags, strategy…"
            className="w-72 pl-8"
            aria-label="Search backtest runs"
          />
        </div>

        <Select
          value={status}
          onValueChange={(value) => {
            setStatus(value as BacktestRunStatus | 'all')
            setOffset(0)
          }}
        >
          <SelectTrigger className="w-40" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {BACKTEST_RUN_STATUSES.map((value) => (
              <SelectItem key={value} value={value}>
                {value[0]?.toUpperCase()}
                {value.slice(1)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Input
          type="date"
          value={dateFrom}
          onChange={(event) => {
            setDateFrom(event.target.value)
            setOffset(0)
          }}
          className="w-40"
          aria-label="Filter from date"
        />
        <Input
          type="date"
          value={dateTo}
          onChange={(event) => {
            setDateTo(event.target.value)
            setOffset(0)
          }}
          className="w-40"
          aria-label="Filter to date"
        />

        <Select value={sortValue} onValueChange={(value) => setSortValue(value as SortValue)}>
          <SelectTrigger className="w-52" aria-label="Sort backtest runs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {SORT_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isLoading && (
        <div className="space-y-2">
          {SKELETON_KEYS.map((key) => (
            <Skeleton key={key} className="h-12" />
          ))}
        </div>
      )}

      {isError && (
        <ErrorState
          message={getErrorMessage(error, 'Unable to load backtest runs.')}
          onRetry={() => refetch()}
        />
      )}

      {!isLoading && !isError && data && data.items.length === 0 && !hasFilters && (
        <EmptyState
          title="No backtest runs yet"
          description="Run a strategy against a dataset to create your first permanent experiment record."
          action={
            <Button asChild>
              <Link to="/backtests">Run Backtest</Link>
            </Button>
          }
        />
      )}

      {!isLoading && !isError && data && data.items.length === 0 && hasFilters && (
        <EmptyState
          title="No runs match your filters"
          description="Try a different search term, status, or date range."
        />
      )}

      {!isLoading && !isError && data && data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Run ID</th>
                  <th className="px-3 py-2 font-medium">Experiment</th>
                  <th className="px-3 py-2 font-medium">Strategy</th>
                  <th className="px-3 py-2 font-medium">Dataset</th>
                  <th className="px-3 py-2 font-medium">Date</th>
                  <th className="px-3 py-2 font-medium">Profit</th>
                  <th className="px-3 py-2 font-medium">Win Rate</th>
                  <th className="px-3 py-2 font-medium">Trades</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((run) => (
                  <tr key={run.id} className="border-t border-border">
                    <td className="px-3 py-2 font-mono text-xs">{run.id}</td>
                    <td className="px-3 py-2">
                      <div className="space-y-1">
                        <p>{run.experiment_name ?? '—'}</p>
                        <p className="text-xs text-muted-foreground">
                          Research {run.research_completion_pct}%
                        </p>
                      </div>
                    </td>
                    <td className="px-3 py-2">{run.strategy_name}</td>
                    <td className="px-3 py-2">{run.dataset_name}</td>
                    <td className="px-3 py-2">{formatDate(run.execution_completed_at)}</td>
                    <td
                      className={`px-3 py-2 font-medium ${
                        run.net_profit >= 0 ? 'text-emerald-600' : 'text-red-600'
                      }`}
                    >
                      {formatCurrency(run.net_profit)}
                    </td>
                    <td className="px-3 py-2">{formatPercent(run.win_rate_pct)}</td>
                    <td className="px-3 py-2">{run.trade_count}</td>
                    <td className="px-3 py-2">
                      <Badge variant={run.status === 'completed' ? 'default' : 'destructive'}>
                        {run.status}
                      </Badge>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <Button asChild variant="outline" size="sm">
                          <Link to={`/backtests/runs/${run.id}`}>View</Link>
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-destructive"
                          onClick={() => setPendingDelete(run)}
                        >
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-6 flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {data.total} {data.total === 1 ? 'run' : 'runs'}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={offset + PAGE_SIZE >= data.total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}

      <DeleteBacktestRunDialog
        run={pendingDelete}
        onOpenChange={(open) => !open && setPendingDelete(null)}
        onConfirm={() => {
          if (!pendingDelete) return
          deleteRun.mutate(pendingDelete.id)
          setPendingDelete(null)
        }}
        isDeleting={deleteRun.isPending}
      />
    </div>
  )
}
