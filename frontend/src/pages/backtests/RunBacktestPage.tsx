import { ArrowRight, Search } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Breadcrumbs, type Crumb } from '@/components/common/Breadcrumbs'
import { ErrorState } from '@/components/common/ErrorState'
import { PageHeader } from '@/components/common/PageHeader'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { BacktestProgressBar } from '@/features/backtests/components/BacktestProgressBar'
import { ExecutionResultCard } from '@/features/backtests/components/ExecutionResultCard'
import { RunBacktestForm } from '@/features/backtests/components/RunBacktestForm'
import { BacktestCancelledError, executeBacktest } from '@/features/backtests/api'
import type { BacktestJobProgress, BacktestJobResult } from '@/features/backtests/types'
import { useBacktestRun } from '@/features/backtest-runs/queries'
import { backtestRunToExecutionResult } from '@/features/backtest-runs/utils'
import { selectLibraryStrategy } from '@/features/backtests/workflow'
import { updateWorkflow, useWorkflow } from '@/features/backtests/workflowStore'
import { useLibraryStrategy } from '@/features/strategy-library/queries'
import { useScrollRestoration } from '@/hooks/useScrollRestoration'
import { getErrorMessage } from '@/lib/apiClient'

/**
 * Step four of the research workflow: configure and run.
 *
 * `?library=<id>` is how the Strategy Library hands a strategy over. The form's
 * own state lives in the workflow store, so arriving here from the library, a
 * saved result, or the sidebar all land on the same configuration.
 */
export default function RunBacktestPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const state = useWorkflow()
  const [receipt, setReceipt] = useState<BacktestJobResult | null>(null)
  const [progress, setProgress] = useState<BacktestJobProgress | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [isCancelling, setIsCancelling] = useState(false)
  const cancelRef = useRef<(() => Promise<void>) | null>(null)

  const requestedLibraryId = searchParams.get('library')

  useEffect(() => {
    if (!requestedLibraryId) return
    updateWorkflow((current) => selectLibraryStrategy(current, requestedLibraryId))
    // Consumed: leaving it in the URL would re-apply on every later render and
    // undo a strategy change made in the form.
    setSearchParams({}, { replace: true })
  }, [requestedLibraryId, setSearchParams])

  const activeLibraryId = state.source === 'library' ? state.libraryStrategyId : ''
  const libraryStrategy = useLibraryStrategy(activeLibraryId)
  const strategyName = state.source === 'library' ? libraryStrategy.data?.name : undefined

  // The job hands back a receipt, not the replay. The result below is read from
  // the saved run - one request, cached by TanStack Query, instead of the whole
  // payload riding along on every progress poll.
  const savedRun = useBacktestRun(receipt?.run_id ?? '')
  const result = savedRun.data ? backtestRunToExecutionResult(savedRun.data) : null

  useScrollRestoration('run-backtest')

  const crumbs: Crumb[] =
    state.source === 'library'
      ? [
          { label: 'Strategy Library', to: '/strategy-library' },
          ...(activeLibraryId
            ? [
                {
                  label: strategyName ?? activeLibraryId,
                  to: `/strategy-library/${activeLibraryId}`,
                },
              ]
            : []),
          { label: 'Run backtest' },
        ]
      : [{ label: 'Backtests', to: '/backtests/runs' }, { label: 'Run backtest' }]

  async function handleCancel() {
    if (!cancelRef.current) return
    setIsCancelling(true)
    try {
      await cancelRef.current()
    } finally {
      setIsCancelling(false)
    }
  }

  return (
    <div>
      <Breadcrumbs items={crumbs} />

      <PageHeader
        title={strategyName ? `Run ${strategyName}` : 'Run Backtest'}
        description="Configure a strategy, choose a dataset, and replay it with full execution detail."
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="/strategy-library">
                <Search className="size-4" />
                Browse library
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/backtests/runs">View saved runs</Link>
            </Button>
          </>
        }
      />

      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      {progress && (
        <div className="mb-6">
          <BacktestProgressBar
            progressPct={progress.progressPct}
            message={progress.message}
            barsProcessed={progress.barsProcessed}
            totalBars={progress.totalBars}
            onCancel={isRunning ? handleCancel : undefined}
            isCancelling={isCancelling}
          />
        </div>
      )}

      <RunBacktestForm
        state={state}
        isSubmitting={isRunning}
        onSubmit={async (input) => {
          setError(null)
          setReceipt(null)
          setProgress({
            progressPct: 0,
            message: 'Starting backtest…',
            barsProcessed: null,
            totalBars: null,
          })
          setIsRunning(true)

          const { result: run, cancel } = executeBacktest(input, setProgress)
          cancelRef.current = cancel

          try {
            setReceipt(await run)
          } catch (err) {
            if (err instanceof BacktestCancelledError) {
              setProgress(null)
              return
            }
            setProgress(null)
            setError(getErrorMessage(err, 'Unable to run this backtest.'))
          } finally {
            setIsRunning(false)
            cancelRef.current = null
          }
        }}
      />

      {receipt && (
        <div className="mt-8 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-muted/30 px-4 py-3 text-sm">
            <span>
              This run was saved permanently. Open it to inspect trades, bars and decisions.
            </span>
            <Button asChild size="sm">
              <Link to={`/backtests/runs/${receipt.run_id}`}>
                Open saved run
                <ArrowRight className="size-4" />
              </Link>
            </Button>
          </div>

          {receipt.warnings.length > 0 && (
            <ul className="space-y-1 rounded-md border border-border bg-muted/30 p-3 text-sm">
              {receipt.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}

          {savedRun.isError ? (
            <ErrorState
              message={getErrorMessage(savedRun.error, 'Unable to load the saved run.')}
              onRetry={() => savedRun.refetch()}
            />
          ) : result ? (
            <ExecutionResultCard result={result} />
          ) : (
            <div className="space-y-4">
              <Skeleton className="h-40" />
              <Skeleton className="h-96" />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
