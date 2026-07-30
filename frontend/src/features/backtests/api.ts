import { api, ApiError } from '@/lib/apiClient'

import type { BacktestExecuteInput, BacktestJobProgress, BacktestJobResult } from './types'

const POLL_INTERVAL_MS = 1000

export class BacktestCancelledError extends Error {
  readonly code = 'CANCELLED'

  constructor() {
    super('Backtest cancelled')
    this.name = 'BacktestCancelledError'
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

export interface ExecuteBacktestHandle {
  result: Promise<BacktestJobResult>
  cancel: () => Promise<void>
}

export function executeBacktest(
  input: BacktestExecuteInput,
  onProgress?: (progress: BacktestJobProgress) => void,
): ExecuteBacktestHandle {
  let jobId: string | null = null
  let cancelRequested = false

  const cancel = async () => {
    cancelRequested = true
    if (jobId) {
      await api.post(`/jobs/${jobId}/cancel`)
    }
  }

  const result = (async () => {
    onProgress?.({
      progressPct: 0,
      message: 'Starting backtest…',
      barsProcessed: null,
      totalBars: null,
    })

    const { job_id: submittedJobId } = await api.post<{ job_id: string }>(
      '/backtests/execute',
      input,
    )
    jobId = submittedJobId

    while (true) {
      if (cancelRequested) {
        throw new BacktestCancelledError()
      }

      // eslint-disable-next-line no-await-in-loop -- intentional job polling
      const job = await api.get<BacktestJob>(`/jobs/${submittedJobId}`)
      onProgress?.({
        progressPct: job.progress_pct,
        message: job.progress_message || 'Running backtest…',
        barsProcessed: job.bars_processed,
        totalBars: job.total_bars,
      })

      if (job.status === 'completed') {
        if (!job.result) {
          throw new ApiError(500, 'INTERNAL_ERROR', 'Backtest finished without a result.')
        }
        onProgress?.({
          progressPct: 100,
          message: 'Backtest complete',
          barsProcessed: job.bars_processed,
          totalBars: job.total_bars,
        })
        return job.result
      }

      if (job.status === 'cancelled' || cancelRequested) {
        throw new BacktestCancelledError()
      }

      if (job.status === 'failed') {
        throw new ApiError(
          500,
          'BACKTEST_FAILED',
          job.error_message || 'The backtest failed.',
        )
      }

      // eslint-disable-next-line no-await-in-loop -- intentional job polling
      await sleep(POLL_INTERVAL_MS)
    }
  })()

  return { result, cancel }
}

interface BacktestJob {
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress_pct: number
  progress_message: string
  bars_processed: number | null
  total_bars: number | null
  result: BacktestJobResult | null
  error_message: string | null
}
