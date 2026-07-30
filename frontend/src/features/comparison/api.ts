import { api } from '@/lib/apiClient'

import type { ComparisonReport } from './types'

export function fetchRunComparison(runIds: string[]): Promise<ComparisonReport> {
  return api.post<ComparisonReport>('/backtests/runs/compare', { run_ids: runIds })
}
