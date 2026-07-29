import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { qk } from '@/lib/queryKeys'

import {
  deleteBacktestRun,
  fetchBacktestRun,
  fetchBacktestRuns,
  updateBacktestRunResearch,
} from './api'
import type { BacktestRunListParams, BacktestRunResearchInput } from './types'

export function useBacktestRuns(params: BacktestRunListParams) {
  return useQuery({
    queryKey: qk.backtestRuns.list(params),
    queryFn: () => fetchBacktestRuns(params),
  })
}

export function useBacktestRun(id: string) {
  return useQuery({
    queryKey: qk.backtestRuns.detail(id),
    queryFn: () => fetchBacktestRun(id),
    enabled: id.length > 0,
  })
}

export function useUpdateBacktestRunResearch(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: BacktestRunResearchInput) => updateBacktestRunResearch(id, input),
    onSuccess: (run) => {
      queryClient.setQueryData(qk.backtestRuns.detail(id), run)
      queryClient.invalidateQueries({ queryKey: qk.backtestRuns.all })
      return run
    },
  })
}

export function useDeleteBacktestRun() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteBacktestRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.backtestRuns.all })
    },
  })
}
