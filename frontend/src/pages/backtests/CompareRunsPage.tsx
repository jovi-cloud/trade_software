import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Breadcrumbs } from '@/components/common/Breadcrumbs'
import { ErrorState } from '@/components/common/ErrorState'
import { PageHeader } from '@/components/common/PageHeader'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ComparisonReportPanel } from '@/features/comparison/components/ComparisonReportPanel'
import { useRunComparison } from '@/features/comparison/queries'
import { getErrorMessage } from '@/lib/apiClient'

function parseRunIds(value: string | null): string[] {
  if (!value) return []
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

export default function CompareRunsPage() {
  const [searchParams] = useSearchParams()
  const runIds = useMemo(() => parseRunIds(searchParams.get('runs')), [searchParams])
  const { data, isLoading, isError, error, refetch } = useRunComparison(runIds)

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: 'Runs', to: '/backtests/runs' },
          { label: 'Compare' },
        ]}
      />

      <PageHeader
        title="Compare Runs"
        description="Side-by-side comparison of completed backtests using persisted analytics."
        actions={
          <Button variant="outline" asChild>
            <Link to="/backtests/runs">Back to runs</Link>
          </Button>
        }
      />

      {runIds.length < 2 && (
        <p className="mb-6 text-sm text-muted-foreground">
          Select at least two runs from the runs list, then open Compare.
        </p>
      )}

      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-96" />
        </div>
      )}

      {isError && (
        <ErrorState
          message={getErrorMessage(error, 'Unable to load this comparison.')}
          onRetry={() => refetch()}
        />
      )}

      {!isLoading && !isError && data && <ComparisonReportPanel report={data} />}
    </div>
  )
}
