import { api } from '@/lib/apiClient'

import type {
  BacktestRun,
  BacktestRunListItem,
  BacktestRunListParams,
  BacktestRunResearchInput,
} from './types'

interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export function fetchBacktestRuns(
  params: BacktestRunListParams,
): Promise<Page<BacktestRunListItem>> {
  return api.get<Page<BacktestRunListItem>>('/backtests/runs', { params })
}

export function fetchBacktestRun(id: string): Promise<BacktestRun> {
  return api.get<BacktestRun>(`/backtests/runs/${id}`)
}

export function updateBacktestRunResearch(
  id: string,
  input: BacktestRunResearchInput,
): Promise<BacktestRun> {
  return api.patch<BacktestRun>(`/backtests/runs/${id}`, input)
}

export function deleteBacktestRun(id: string): Promise<void> {
  return api.delete<void>(`/backtests/runs/${id}`)
}
