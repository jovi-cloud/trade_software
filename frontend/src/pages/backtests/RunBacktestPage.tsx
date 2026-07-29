import { useState } from 'react'

import { PageHeader } from '@/components/common/PageHeader'
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
        <div className="mt-8">
          <ExecutionResultCard result={result} />
        </div>
      )}
    </div>
  )
}
