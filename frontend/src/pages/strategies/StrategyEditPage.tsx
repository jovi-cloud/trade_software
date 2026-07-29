import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { PageHeader } from '@/components/common/PageHeader'
import { Skeleton } from '@/components/ui/skeleton'
import { StrategyForm } from '@/features/strategies/components/StrategyForm'
import { useStrategy, useUpdateStrategy } from '@/features/strategies/queries'
import { getErrorMessage } from '@/lib/apiClient'

export default function StrategyEditPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: strategy, isLoading, isError, error, refetch } = useStrategy(id ?? '')
  const updateStrategy = useUpdateStrategy(id ?? '')
  const [submitError, setSubmitError] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div className="max-w-2xl space-y-4">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-96" />
      </div>
    )
  }

  if (isError || !strategy) {
    return (
      <ErrorState
        message={getErrorMessage(error, 'Unable to load this strategy.')}
        onRetry={() => refetch()}
      />
    )
  }

  return (
    <div>
      <PageHeader
        title={`Edit ${strategy.name}`}
        description="Changes save immediately - there is no version history yet."
      />
      {submitError && <p className="mb-4 text-sm text-destructive">{submitError}</p>}
      <StrategyForm
        submitLabel="Save Changes"
        isSubmitting={updateStrategy.isPending}
        onCancel={() => navigate(`/strategies/${strategy.id}`)}
        initialValues={{
          name: strategy.name,
          description: strategy.description,
          hypothesis: strategy.hypothesis ?? '',
          market_type: strategy.market_type,
          instrument: strategy.instrument,
          timeframe: strategy.timeframe,
          status: strategy.status,
          priority: strategy.priority,
          confidence_level: strategy.confidence_level,
          tags: strategy.tags ?? '',
        }}
        onSubmit={async (input) => {
          setSubmitError(null)
          try {
            await updateStrategy.mutateAsync(input)
            navigate(`/strategies/${strategy.id}`)
          } catch (err) {
            setSubmitError(getErrorMessage(err, 'Unable to save changes.'))
          }
        }}
      />
    </div>
  )
}
