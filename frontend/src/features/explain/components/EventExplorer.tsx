import { useCallback, useRef, useState } from 'react'

import { ErrorState } from '@/components/common/ErrorState'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { MetadataPanel } from '@/features/explain/components/MetadataPanel'
import {
  EXPLAIN_EVENT_LABELS,
  EXPLAIN_LAYER_LABELS,
  STATUS_LABELS,
  formatReasonCode,
} from '@/features/explain/labels'
import { useRunEvents } from '@/features/explain/queries'
import type { ExplainEventListParams } from '@/features/explain/api'
import { getErrorMessage } from '@/lib/apiClient'
import { formatTimestamp } from '@/lib/format'

interface EventExplorerProps {
  runId: string
  initialTradeId?: number | null
  onSelectTrade?: (tradeId: number) => void
}

const LAYER_OPTIONS = ['all', 'system', 'execution', 'decision', 'narrative'] as const

export function EventExplorer({ runId, initialTradeId, onSelectTrade }: EventExplorerProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [filters, setFilters] = useState<ExplainEventListParams>({
    trade_id: initialTradeId ?? undefined,
    sort: 'seq',
    order: 'asc',
  })
  const [selectedSeq, setSelectedSeq] = useState<number | null>(null)

  const { data, isLoading, isError, error, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useRunEvents(runId, filters)

  const events = data?.pages.flatMap((page) => page.items) ?? []
  const total = data?.pages[0]?.total ?? 0
  const selected = events.find((event) => event.seq === selectedSeq) ?? null

  const handleScroll = useCallback(() => {
    const node = scrollRef.current
    if (!node || !hasNextPage || isFetchingNextPage) return
    const nearBottom = node.scrollTop + node.clientHeight >= node.scrollHeight - 120
    if (nearBottom) {
      void fetchNextPage()
    }
  }, [fetchNextPage, hasNextPage, isFetchingNextPage])

  if (isLoading) {
    return <Skeleton className="h-96 w-full" />
  }

  if (isError) {
    return (
      <ErrorState message={getErrorMessage(error, 'Unable to load execution events.')} />
    )
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Execution Event Explorer</CardTitle>
          <p className="text-sm text-muted-foreground">
            {total.toLocaleString()} events — scroll to load more
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <EventFilters filters={filters} onChange={setFilters} />

          <div
            ref={scrollRef}
            onScroll={handleScroll}
            className="max-h-[32rem] space-y-2 overflow-y-auto pr-1"
          >
            {events
              .filter((event) => event.layer !== 'narrative')
              .map((event) => (
                <button
                  key={event.event_id}
                  type="button"
                  onClick={() => setSelectedSeq(event.seq)}
                  className={`w-full rounded-md border p-3 text-left text-sm transition-colors ${
                    selectedSeq === event.seq
                      ? 'border-primary bg-primary/5'
                      : 'border-border bg-muted/20 hover:bg-muted/40'
                  }`}
                >
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <span className="font-medium">
                      {EXPLAIN_EVENT_LABELS[event.event_type] ?? event.event_type}
                    </span>
                    <Badge variant="outline">{STATUS_LABELS[event.status]}</Badge>
                    <Badge variant="secondary">{EXPLAIN_LAYER_LABELS[event.layer]}</Badge>
                  </div>
                  <p className="line-clamp-2 text-muted-foreground">{event.message}</p>
                  <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
                    {event.timestamp_ms > 0 && <span>{formatTimestamp(event.timestamp_ms)}</span>}
                    {event.bar_index !== null && event.bar_index !== undefined && (
                      <span>Bar {event.bar_index + 1}</span>
                    )}
                    {(event.trade_id ?? event.trade_seq) && (
                      <span
                        role="button"
                        tabIndex={0}
                        className="text-primary underline-offset-2 hover:underline"
                        onClick={(clickEvent) => {
                          clickEvent.stopPropagation()
                          const tradeId = event.trade_id ?? event.trade_seq
                          if (tradeId) onSelectTrade?.(tradeId)
                        }}
                        onKeyDown={(keyEvent) => {
                          if (keyEvent.key === 'Enter' || keyEvent.key === ' ') {
                            keyEvent.stopPropagation()
                            const tradeId = event.trade_id ?? event.trade_seq
                            if (tradeId) onSelectTrade?.(tradeId)
                          }
                        }}
                      >
                        Trade {event.trade_id ?? event.trade_seq}
                      </span>
                    )}
                    <span>{formatReasonCode(event.reason_code)}</span>
                  </div>
                </button>
              ))}
            {isFetchingNextPage && <Skeleton className="h-12 w-full" />}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Event Details</CardTitle>
        </CardHeader>
        <CardContent>
          {selected ? (
            <MetadataPanel event={selected} />
          ) : (
            <p className="text-sm text-muted-foreground">
              Select an event to inspect its metadata.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function EventFilters({
  filters,
  onChange,
}: {
  filters: ExplainEventListParams
  onChange: (next: ExplainEventListParams) => void
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <div className="space-y-1">
        <Label htmlFor="event-search">Search</Label>
        <Input
          id="event-search"
          placeholder="Search message or reason"
          value={filters.q ?? ''}
          onChange={(event) => onChange({ ...filters, q: event.target.value || undefined })}
        />
      </div>
      <div className="space-y-1">
        <Label>Layer</Label>
        <Select
          value={filters.layer ?? 'all'}
          onValueChange={(value) =>
            onChange({
              ...filters,
              layer: value === 'all' ? undefined : (value as ExplainEventListParams['layer']),
            })
          }
        >
          <SelectTrigger>
            <SelectValue placeholder="All layers" />
          </SelectTrigger>
          <SelectContent>
            {LAYER_OPTIONS.map((layer) => (
              <SelectItem key={layer} value={layer}>
                {layer === 'all' ? 'All layers' : EXPLAIN_LAYER_LABELS[layer]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1">
        <Label htmlFor="trade-filter">Trade</Label>
        <Input
          id="trade-filter"
          type="number"
          min={1}
          placeholder="Any"
          value={filters.trade_id ?? ''}
          onChange={(event) =>
            onChange({
              ...filters,
              trade_id: event.target.value ? Number(event.target.value) : undefined,
            })
          }
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="order-filter">Order</Label>
        <Input
          id="order-filter"
          type="number"
          min={1}
          placeholder="Any"
          value={filters.order_id ?? ''}
          onChange={(event) =>
            onChange({
              ...filters,
              order_id: event.target.value ? Number(event.target.value) : undefined,
            })
          }
        />
      </div>
    </div>
  )
}
