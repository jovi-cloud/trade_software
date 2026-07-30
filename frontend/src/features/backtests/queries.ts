import { useMutation } from '@tanstack/react-query'

import { executeBacktest } from './api'
import type { BacktestExecuteInput, BacktestJobProgress } from './types'

interface ExecuteBacktestVariables {
  input: BacktestExecuteInput
  onProgress?: (progress: BacktestJobProgress) => void
}

export function useExecuteBacktest() {
  return useMutation({
    mutationFn: ({ input, onProgress }: ExecuteBacktestVariables) =>
      executeBacktest(input, onProgress).result,
  })
}
