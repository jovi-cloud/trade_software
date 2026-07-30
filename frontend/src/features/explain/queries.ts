import { useEffect } from 'react'
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query'

import { qk } from '@/lib/queryKeys'

import {
  fetchBarInspection,
  fetchDecisionSummary,
  fetchDecisions,
  fetchRunEvents,
  fetchTradeEvents,
  fetchTradeInspection,
} from './api'
import type { ExplainEventListParams } from './api'

const PAGE_SIZE = 50

/** Bars per decision-log request. Matches what fits on screen without scrolling
 *  the whole 194k-bar log into memory to show fifty rows of it. */
export const DECISION_PAGE_SIZE = 100

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

/** One window of the per-bar decision log. */
export function useDecisions(runId: string, start: number, enabled = true) {
  return useQuery({
    queryKey: qk.explain.decisions(runId, start, DECISION_PAGE_SIZE),
    queryFn: () => fetchDecisions(runId, { start, count: DECISION_PAGE_SIZE }),
    enabled: enabled && runId.length > 0 && start >= 0,
    // Runs are append-only, so a window that has been read once can never
    // change - there is nothing to revalidate.
    staleTime: Infinity,
  })
}

/** Whole-run condition tallies. One aggregate over the log, not a page of it. */
export function useDecisionSummary(runId: string, enabled = true) {
  return useQuery({
    queryKey: qk.explain.decisionSummary(runId),
    queryFn: () => fetchDecisionSummary(runId),
    enabled: enabled && runId.length > 0,
    staleTime: Infinity,
  })
}
