import type { BacktestRun } from '@/features/backtest-runs/types'
import type { components } from '@/types/api'

export type BacktestExecuteInput = components['schemas']['BacktestExecuteRequest']

/** In-memory replay result shape shared by saved runs and live execution UI. */
export type ExecutionResult = Pick<
  BacktestRun,
  | 'completed'
  | 'bars_processed'
  | 'execution_time_ms'
  | 'errors'
  | 'warnings'
  | 'strategy_logs'
  | 'orders'
  | 'trades'
  | 'final_cash'
  | 'position_closed'
  | 'trade_count'
  | 'metrics'
  | 'analytics'
  | 'equity_history'
  | 'candles'
  | 'entry_markers'
  | 'exit_markers'
  | 'trailing_stop_points'
  | 'explain_level'
> & {
  run_id?: string | null
  dataset_version_id?: string | null
  dataset_version_number?: number | null
  dataset_fingerprint?: string | null
  explain_events?: BacktestRun['lifecycle_events']
}

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
