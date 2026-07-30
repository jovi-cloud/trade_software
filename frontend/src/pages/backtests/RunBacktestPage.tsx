import { ArrowRight, Search } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Breadcrumbs, type Crumb } from '@/components/common/Breadcrumbs'
import { PageHeader } from '@/components/common/PageHeader'
import { Button } from '@/components/ui/button'
import { ExecutionResultCard } from '@/features/backtests/components/ExecutionResultCard'
import { RunBacktestForm } from '@/features/backtests/components/RunBacktestForm'
import { useExecuteBacktest } from '@/features/backtests/queries'
import type { ExecutionResult } from '@/features/backtests/types'
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
  const executeBacktest = useExecuteBacktest()
  const [result, setResult] = useState<ExecutionResult | null>(null)
  const [error, setError] = useState<string | null>(null)

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

      <RunBacktestForm
        state={state}
        isSubmitting={executeBacktest.isPending}
        onSubmit={async (input) => {
          setError(null)
          setResult(null)
          try {
            setResult(await executeBacktest.mutateAsync(input))
          } catch (err) {
            setError(getErrorMessage(err, 'Unable to run this backtest.'))
          }
        }}
      />

      {result && (
        <div className="mt-8 space-y-4">
          {result.run_id && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-muted/30 px-4 py-3 text-sm">
              <span>
                This run was saved permanently. Open it to inspect trades, bars and decisions.
              </span>
              <Button asChild size="sm">
                <Link to={`/backtests/runs/${result.run_id}`}>
                  Open saved run
                  <ArrowRight className="size-4" />
                </Link>
              </Button>
            </div>
          )}
          <ExecutionResultCard result={result} />
        </div>
      )}
    </div>
  )
}
