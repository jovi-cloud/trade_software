import type { components } from '@/types/api'

export type BacktestExecuteInput = components['schemas']['BacktestExecuteRequest']
export type ExecutionResult = components['schemas']['ExecutionResultRead']

/**
 * What a finished job hands back: the saved run's id plus headline counts.
 *
 * Deliberately not the replay. The job record is re-serialised on every
 * progress poll, so the payload has to stay bounded; the run itself is read
 * once, by id, from `/backtests/runs/{run_id}`.
 */
export type BacktestJobResult = components['schemas']['BacktestJobResultRead']

export interface BacktestJobProgress {
  progressPct: number
  message: string
  barsProcessed: number | null
  totalBars: number | null
}
