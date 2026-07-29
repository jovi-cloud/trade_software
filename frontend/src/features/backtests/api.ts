import { api } from '@/lib/apiClient'

import type { BacktestExecuteInput, ExecutionResult } from './types'

export function executeBacktest(input: BacktestExecuteInput): Promise<ExecutionResult> {
  return api.post<ExecutionResult>('/backtests/execute', input)
}
