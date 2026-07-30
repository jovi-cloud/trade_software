import { useEffect } from 'react'
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'

import { qk } from '@/lib/queryKeys'

import {
  fetchBarInspection,
  fetchRunEvents,
  fetchTradeEvents,
  fetchTradeInspection,
} from './api'
import type { ExplainEventListParams } from './api'

const PAGE_SIZE = 50

export function useRunEvents(runId: string, filters: ExplainEventListParams) {
  return useInfiniteQuery({
    queryKey: qk.explain.events(runId, filters as Record<string, unknown>),
    queryFn: ({ pageParam = 0 }) =>
      fetchRunEvents(runId, {
        ...filters,
        limit: PAGE_SIZE,
        offset: pageParam,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      const next = lastPage.offset + lastPage.items.length
      return next < lastPage.total ? next : undefined
    },
    enabled: runId.length > 0,
  })
}

export function useTradeInspection(runId: string, tradeId: number | null) {
  return useQuery({
    queryKey: qk.explain.trade(runId, tradeId ?? 0),
    queryFn: () => fetchTradeInspection(runId, tradeId!),
    enabled: runId.length > 0 && tradeId !== null && tradeId > 0,
  })
}

export function useTradeEvents(runId: string, tradeId: number | null) {
  return useQuery({
    queryKey: qk.explain.tradeEvents(runId, tradeId ?? 0),
    queryFn: () => fetchTradeEvents(runId, tradeId!, { limit: 200 }),
    enabled: runId.length > 0 && tradeId !== null && tradeId > 0,
  })
}

export function useBarInspection(runId: string, barIndex: number | null) {
  const queryClient = useQueryClient()

  const query = useQuery({
    queryKey: qk.explain.bar(runId, barIndex ?? 0),
    queryFn: () => fetchBarInspection(runId, barIndex!),
    enabled: runId.length > 0 && barIndex !== null && barIndex >= 0,
  })

  useEffect(() => {
    if (runId.length === 0 || barIndex === null || barIndex < 0) return
    for (const neighbour of [barIndex - 1, barIndex + 1]) {
      if (neighbour >= 0) {
        void queryClient.prefetchQuery({
          queryKey: qk.explain.bar(runId, neighbour),
          queryFn: () => fetchBarInspection(runId, neighbour),
        })
      }
    }
  }, [barIndex, queryClient, runId])

  return query
}
