import { Link } from 'react-router-dom'
import { useState } from 'react'

import { PageHeader } from '@/components/common/PageHeader'
import { Button } from '@/components/ui/button'
import { ExecutionResultCard } from '@/features/backtests/components/ExecutionResultCard'
import { RunBacktestForm } from '@/features/backtests/components/RunBacktestForm'
import { useExecuteBacktest } from '@/features/backtests/queries'
import type { ExecutionResult } from '@/features/backtests/types'
import { getErrorMessage } from '@/lib/apiClient'

export default function RunBacktestPage() {
  const executeBacktest = useExecuteBacktest()
  const [result, setResult] = useState<ExecutionResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  return (
    <div>
      <PageHeader
        title="Run Backtest"
        description="Replay a saved strategy against a dataset and analyse the results with charts and trade markers."
        actions={
          <Button variant="outline" asChild>
            <Link to="/backtests/runs">View saved runs</Link>
          </Button>
        }
      />

      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}

      <RunBacktestForm
        isSubmitting={executeBacktest.isPending}
        onSubmit={async (input) => {
          setError(null)
          setResult(null)
          try {
            const execution = await executeBacktest.mutateAsync(input)
            setResult(execution)
          } catch (err) {
            setError(getErrorMessage(err, 'Unable to run this backtest.'))
          }
        }}
      />

      {result && (
        <div className="mt-8 space-y-4">
          {result.run_id && (
            <div className="flex items-center justify-between rounded-md border border-border bg-muted/30 px-4 py-3 text-sm">
              <span>This run was saved permanently.</span>
              <Button asChild size="sm">
                <Link to={`/backtests/runs/${result.run_id}`}>Open saved run</Link>
              </Button>
            </div>
          )}
          <ExecutionResultCard result={result} />
        </div>
      )}
    </div>
  )
}
