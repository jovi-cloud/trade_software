import { Plus, Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { PageHeader } from '@/components/common/PageHeader'
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
import { DeleteStrategyDialog } from '@/features/strategies/components/DeleteStrategyDialog'
import { StrategyCard } from '@/features/strategies/components/StrategyCard'
import { useDeleteStrategy, useStrategies } from '@/features/strategies/queries'
import { STRATEGY_STATUSES } from '@/features/strategies/types'
import type { Strategy, StrategyStatus } from '@/features/strategies/types'
import { getErrorMessage } from '@/lib/apiClient'

const PAGE_SIZE = 20

const SORT_OPTIONS = [
  { value: 'updated_at:desc', label: 'Recently updated' },
  { value: 'updated_at:asc', label: 'Oldest updated' },
  { value: 'name:asc', label: 'Name A–Z' },
  { value: 'name:desc', label: 'Name Z–A' },
] as const

type SortValue = (typeof SORT_OPTIONS)[number]['value']

const SKELETON_KEYS = ['sk-1', 'sk-2', 'sk-3', 'sk-4', 'sk-5', 'sk-6']

/** Every list has: search, status filter, sort, empty/loading/error states, soft delete. */
export default function StrategyListPage() {
  const [searchInput, setSearchInput] = useState('')
  const [q, setQ] = useState('')
  const [status, setStatus] = useState<StrategyStatus | 'all'>('all')
  const [sortValue, setSortValue] = useState<SortValue>('updated_at:desc')
  const [offset, setOffset] = useState(0)
  const [pendingDelete, setPendingDelete] = useState<Strategy | null>(null)

  useEffect(() => {
    const timeout = setTimeout(() => {
      setQ(searchInput.trim())
      setOffset(0)
    }, 300)
    return () => clearTimeout(timeout)
  }, [searchInput])

  const [sort, order] = sortValue.split(':') as ['updated_at' | 'name', 'asc' | 'desc']

  const params = useMemo(
    () => ({
      q: q || undefined,
      status: status === 'all' ? undefined : status,
      sort,
      order,
      limit: PAGE_SIZE,
      offset,
    }),
    [q, status, sort, order, offset],
  )

  const { data, isLoading, isError, error, refetch } = useStrategies(params)
  const deleteStrategy = useDeleteStrategy()

  const hasFilters = q.length > 0 || status !== 'all'

  return (
    <div>
      <PageHeader
        title="Strategies"
        description="Manage the trading ideas you're researching."
        actions={
          <Button asChild>
            <Link to="/strategies/new">
              <Plus /> New Strategy
            </Link>
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search by name…"
            className="w-64 pl-8"
            aria-label="Search strategies by name"
          />
        </div>

        <Select
          value={status}
          onValueChange={(value) => {
            setStatus(value as StrategyStatus | 'all')
            setOffset(0)
          }}
        >
          <SelectTrigger className="w-40" aria-label="Filter by status">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            {STRATEGY_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {s[0]?.toUpperCase()}
                {s.slice(1)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={sortValue} onValueChange={(value) => setSortValue(value as SortValue)}>
          <SelectTrigger className="w-48" aria-label="Sort strategies">
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
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {SKELETON_KEYS.map((key) => (
            <Skeleton key={key} className="h-44" />
          ))}
        </div>
      )}

      {isError && (
        <ErrorState
          message={getErrorMessage(error, 'Unable to load strategies.')}
          onRetry={() => refetch()}
        />
      )}

      {!isLoading && !isError && data && data.items.length === 0 && !hasFilters && (
        <EmptyState
          title="No strategies yet"
          description="Create your first strategy idea to start the research loop."
          action={
            <Button asChild>
              <Link to="/strategies/new">
                <Plus /> New Strategy
              </Link>
            </Button>
          }
        />
      )}

      {!isLoading && !isError && data && data.items.length === 0 && hasFilters && (
        <EmptyState
          title="No strategies match your filters"
          description="Try a different search term or status filter."
        />
      )}

      {!isLoading && !isError && data && data.items.length > 0 && (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.items.map((strategy) => (
              <StrategyCard
                key={strategy.id}
                strategy={strategy}
                onDeleteRequest={setPendingDelete}
              />
            ))}
          </div>

          <div className="mt-6 flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {data.total} {data.total === 1 ? 'strategy' : 'strategies'}
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

      <DeleteStrategyDialog
        strategy={pendingDelete}
        onOpenChange={(open) => !open && setPendingDelete(null)}
        onConfirm={() => {
          if (!pendingDelete) return
          deleteStrategy.mutate(pendingDelete.id)
          setPendingDelete(null)
        }}
        isDeleting={deleteStrategy.isPending}
      />
    </div>
  )
}
