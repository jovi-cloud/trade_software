import { useMutation } from '@tanstack/react-query'

import { executeBacktest } from './api'
import type { BacktestExecuteInput } from './types'

export function useExecuteBacktest() {
  return useMutation({
    mutationFn: (input: BacktestExecuteInput) => executeBacktest(input),
  })
}
