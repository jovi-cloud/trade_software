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
import { DatasetCard } from '@/features/datasets/components/DatasetCard'
import { DeleteDatasetDialog } from '@/features/datasets/components/DeleteDatasetDialog'
import { useDeleteDataset, useDatasets } from '@/features/datasets/queries'
import { TIMEFRAMES, type Dataset, type DatasetSort, type Timeframe } from '@/features/datasets/types'
import { getErrorMessage } from '@/lib/apiClient'

const PAGE_SIZE = 20

const SORT_OPTIONS: { value: `${DatasetSort}:${'asc' | 'desc'}`; label: string }[] = [
  { value: 'updated_at:desc', label: 'Recently updated' },
  { value: 'updated_at:asc', label: 'Oldest updated' },
  { value: 'name:asc', label: 'Name A–Z' },
  { value: 'name:desc', label: 'Name Z–A' },
  { value: 'row_count:desc', label: 'Most bars' },
]

type SortValue = (typeof SORT_OPTIONS)[number]['value']

const SKELETON_KEYS = ['sk-1', 'sk-2', 'sk-3', 'sk-4', 'sk-5', 'sk-6']

export default function DataLibraryPage() {
  const [searchInput, setSearchInput] = useState('')
  const [q, setQ] = useState('')
  const [timeframe, setTimeframe] = useState<Timeframe | 'all'>('all')
  const [sortValue, setSortValue] = useState<SortValue>('updated_at:desc')
  const [offset, setOffset] = useState(0)
  const [pendingDelete, setPendingDelete] = useState<Dataset | null>(null)

  useEffect(() => {
    const timeout = setTimeout(() => {
      setQ(searchInput.trim())
      setOffset(0)
    }, 300)
    return () => clearTimeout(timeout)
  }, [searchInput])

  const [sort, order] = sortValue.split(':') as [DatasetSort, 'asc' | 'desc']

  const params = useMemo(
    () => ({
      q: q || undefined,
      timeframe: timeframe === 'all' ? undefined : timeframe,
      sort,
      order,
      limit: PAGE_SIZE,
      offset,
    }),
    [q, timeframe, sort, order, offset],
  )

  const { data, isLoading, isError, error, refetch } = useDatasets(params)
  const deleteDataset = useDeleteDataset()

  const hasFilters = q.length > 0 || timeframe !== 'all'

  return (
    <div>
      <PageHeader
        title="Data library"
        description="Imported market data used for backtests."
        actions={
          <Button asChild>
            <Link to="/data/import">
              <Plus /> Import data
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
            placeholder="Search by name or symbol…"
            className="w-64 pl-8"
            aria-label="Search datasets"
          />
        </div>

        <Select
          value={timeframe}
          onValueChange={(value) => {
            setTimeframe(value as Timeframe | 'all')
            setOffset(0)
          }}
        >
          <SelectTrigger className="w-36" aria-label="Filter by timeframe">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All timeframes</SelectItem>
            {TIMEFRAMES.map((tf) => (
              <SelectItem key={tf} value={tf}>
                {tf}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={sortValue} onValueChange={(value) => setSortValue(value as SortValue)}>
          <SelectTrigger className="w-48" aria-label="Sort datasets">
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
          message={getErrorMessage(error, 'Unable to load datasets.')}
          onRetry={() => refetch()}
        />
      )}

      {!isLoading && !isError && data && data.items.length === 0 && !hasFilters && (
        <EmptyState
          title="No datasets yet"
          description="Import CSV, Excel, or Parquet files to start backtesting."
          action={
            <Button asChild>
              <Link to="/data/import">
                <Plus /> Import data
              </Link>
            </Button>
          }
        />
      )}

      {!isLoading && !isError && data && data.items.length === 0 && hasFilters && (
        <EmptyState
          title="No datasets match your filters"
          description="Try a different search term or timeframe."
        />
      )}

      {!isLoading && !isError && data && data.items.length > 0 && (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.items.map((dataset) => (
              <DatasetCard
                key={dataset.id}
                dataset={dataset}
                onDeleteRequest={setPendingDelete}
              />
            ))}
          </div>

          <div className="mt-6 flex items-center justify-between text-sm text-muted-foreground">
            <span>
              {data.total} {data.total === 1 ? 'dataset' : 'datasets'}
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

      <DeleteDatasetDialog
        dataset={pendingDelete}
        onOpenChange={(open) => !open && setPendingDelete(null)}
        onConfirm={() => {
          if (!pendingDelete) return
          deleteDataset.mutate(pendingDelete.id)
          setPendingDelete(null)
        }}
        isDeleting={deleteDataset.isPending}
      />
    </div>
  )
}
