import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { PageHeader } from '@/components/common/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ResearchJournal } from '@/features/backtest-runs/components/ResearchJournal'
import { useBacktestRun } from '@/features/backtest-runs/queries'
import { backtestRunToExecutionResult } from '@/features/backtest-runs/utils'
import { ExecutionResultCard } from '@/features/backtests/components/ExecutionResultCard'
import { ExplainabilityPanel } from '@/features/explain/components/ExplainabilityPanel'
import { formatCurrency, formatDate, formatDuration } from '@/lib/format'
import { getErrorMessage } from '@/lib/apiClient'

export default function BacktestRunDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const { data: run, isLoading, isError, error, refetch } = useBacktestRun(id)
  const [selectedBarIndex, setSelectedBarIndex] = useState<number | null>(null)

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-48" />
        <Skeleton className="h-96" />
      </div>
    )
  }

  if (isError || !run) {
    return (
      <ErrorState
        message={getErrorMessage(error, 'Unable to load this backtest run.')}
        onRetry={() => refetch()}
      />
    )
  }

  const executionResult = backtestRunToExecutionResult(run)

  return (
    <div>
      <PageHeader
        title="Backtest Run"
        description={`${run.strategy_name} on ${run.dataset_name}`}
        actions={
          <Button variant="outline" asChild>
            <Link to="/backtests/runs">All runs</Link>
          </Button>
        }
      />

      <Card className="mb-6">
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <CardTitle className="text-base">Run configuration snapshot</CardTitle>
          <Badge variant={run.status === 'completed' ? 'default' : 'destructive'}>
            {run.status}
          </Badge>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-sm">
            <div>
              <dt className="text-xs text-muted-foreground">Run ID</dt>
              <dd className="font-mono text-xs">{run.id}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Executed</dt>
              <dd>{formatDate(run.execution_completed_at)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Duration</dt>
              <dd>{formatDuration(run.execution_time_ms)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Engine</dt>
              <dd>{run.engine_version}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Initial capital</dt>
              <dd>{formatCurrency(run.initial_capital)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Commission</dt>
              <dd>{run.commission}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Slippage</dt>
              <dd>{run.slippage}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Dataset hash</dt>
              <dd className="truncate font-mono text-xs">{run.dataset_hash}</dd>
            </div>
          </dl>
          {run.error_message && (
            <p className="mt-4 text-sm text-destructive">{run.error_message}</p>
          )}
        </CardContent>
      </Card>

      <ExecutionResultCard
        result={executionResult}
        selectedBarIndex={selectedBarIndex}
        onBarSelect={setSelectedBarIndex}
      />

      {run.explain_level !== 'none' && (
        <div className="mt-8 max-w-6xl">
          <ExplainabilityPanel
            runId={run.id}
            tradeCount={run.trade_count}
            selectedBarIndex={selectedBarIndex}
            onBarSelect={setSelectedBarIndex}
          />
        </div>
      )}

      <div className="mt-8 max-w-6xl">
        <ResearchJournal run={run} />
      </div>

      <div className="mt-6">
        <Button variant="outline" onClick={() => navigate('/backtests/runs')}>
          Back to runs
        </Button>
      </div>
    </div>
  )
}
