import { Search } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

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
import { LibraryStrategyCard } from '@/features/strategy-library/components/LibraryStrategyCard'
import { RecentAndFavorites } from '@/features/strategy-library/components/RecentAndFavorites'
import { categoryLabel, humanise } from '@/features/strategy-library/categoryMeta'
import { useLibraryFacets, useLibraryStrategies } from '@/features/strategy-library/queries'
import { getFavoriteStrategyIds } from '@/features/strategy-library/storage'
import type { RiskLevel, StrategyCategory, TradingStyle } from '@/features/strategy-library/types'
import { getErrorMessage } from '@/lib/apiClient'

const PAGE_SIZE = 12
const SKELETON_KEYS = ['sk-1', 'sk-2', 'sk-3', 'sk-4', 'sk-5', 'sk-6']

export default function StrategyLibraryListPage() {
  const [searchInput, setSearchInput] = useState('')
  const [q, setQ] = useState('')
  const [category, setCategory] = useState<StrategyCategory | 'all'>('all')
  const [tag, setTag] = useState<string>('all')
  const [riskLevel, setRiskLevel] = useState<RiskLevel | 'all'>('all')
  const [style, setStyle] = useState<TradingStyle | 'all'>('all')
  const [offset, setOffset] = useState(0)
  const [favoriteIds, setFavoriteIds] = useState<string[]>([])

  useEffect(() => {
    setFavoriteIds(getFavoriteStrategyIds())
  }, [])

  useEffect(() => {
    const timeout = setTimeout(() => {
      setQ(searchInput.trim())
      setOffset(0)
    }, 300)
    return () => clearTimeout(timeout)
  }, [searchInput])

  const params = useMemo(
    () => ({
      q: q || undefined,
      category: category === 'all' ? undefined : category,
      tag: tag === 'all' ? undefined : [tag],
      risk_level: riskLevel === 'all' ? undefined : riskLevel,
      style: style === 'all' ? undefined : style,
      limit: PAGE_SIZE,
      offset,
    }),
    [q, category, tag, riskLevel, style, offset],
  )

  const { data, isLoading, isError, error, refetch } = useLibraryStrategies(params)
  const facets = useLibraryFacets()

  const hasFilters =
    q.length > 0 || category !== 'all' || tag !== 'all' || riskLevel !== 'all' || style !== 'all'

  return (
    <div>
      <PageHeader
        title="Strategy Library"
        description="Discover, configure and validate built-in reference strategies."
      />

      <RecentAndFavorites strategies={data?.items ?? []} />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search strategies…"
            className="w-64 pl-8"
            aria-label="Search strategy library"
          />
        </div>

        <Select
          value={category}
          onValueChange={(value) => {
            setCategory(value as StrategyCategory | 'all')
            setOffset(0)
          }}
        >
          <SelectTrigger className="w-44" aria-label="Filter by category">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All categories</SelectItem>
            {(facets.data?.categories ?? []).map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {categoryLabel(item.value as StrategyCategory)} ({item.count})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={tag}
          onValueChange={(value) => {
            setTag(value)
            setOffset(0)
          }}
        >
          <SelectTrigger className="w-40" aria-label="Filter by tag">
            <SelectValue placeholder="Tag" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All tags</SelectItem>
            {(facets.data?.tags ?? []).map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {item.value} ({item.count})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={riskLevel}
          onValueChange={(value) => {
            setRiskLevel(value as RiskLevel | 'all')
            setOffset(0)
          }}
        >
          <SelectTrigger className="w-36" aria-label="Filter by risk level">
            <SelectValue placeholder="Risk" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All risk</SelectItem>
            {(facets.data?.risk_levels ?? []).map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {humanise(item.value)} ({item.count})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={style}
          onValueChange={(value) => {
            setStyle(value as TradingStyle | 'all')
            setOffset(0)
          }}
        >
          <SelectTrigger className="w-36" aria-label="Filter by trading style">
            <SelectValue placeholder="Style" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All styles</SelectItem>
            {(facets.data?.styles ?? []).map((item) => (
              <SelectItem key={item.value} value={item.value}>
                {humanise(item.value)} ({item.count})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {facets.data && facets.data.load_failures.length > 0 && (
        <div className="mb-4 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-300">
          {facets.data.load_failures.length} strategy module
          {facets.data.load_failures.length === 1 ? '' : 's'} failed to load. Some strategies may be
          missing.
        </div>
      )}

      {isLoading && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {SKELETON_KEYS.map((key) => (
            <Skeleton key={key} className="h-48" />
          ))}
        </div>
      )}

      {isError && (
        <ErrorState
          message={getErrorMessage(error, 'Unable to load the strategy library.')}
          onRetry={() => refetch()}
        />
      )}

      {!isLoading && !isError && data && data.items.length === 0 && !hasFilters && (
        <EmptyState
          title="No strategies available"
          description="Built-in strategies could not be loaded."
        />
      )}

      {!isLoading && !isError && data && data.items.length === 0 && hasFilters && (
        <EmptyState
          title="No strategies match your filters"
          description="Try a different search term or filter."
        />
      )}

      {!isLoading && !isError && data && data.items.length > 0 && (
        <>
          <div className="mb-3 flex flex-wrap gap-2">
            <Badge variant="outline">{data.total} strategies</Badge>
            {facets.data && <Badge variant="outline">{facets.data.valid_count} valid</Badge>}
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.items.map((strategy) => (
              <LibraryStrategyCard
                key={strategy.id}
                strategy={strategy}
                isFavorite={favoriteIds.includes(strategy.id)}
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
    </div>
  )
}
