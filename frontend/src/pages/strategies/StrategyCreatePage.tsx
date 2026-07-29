import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { PageHeader } from '@/components/common/PageHeader'
import { StrategyForm } from '@/features/strategies/components/StrategyForm'
import { useCreateStrategy } from '@/features/strategies/queries'
import { getErrorMessage } from '@/lib/apiClient'

export default function StrategyCreatePage() {
  const navigate = useNavigate()
  const createStrategy = useCreateStrategy()
  const [error, setError] = useState<string | null>(null)

  return (
    <div>
      <PageHeader
        title="New Strategy"
        description="Capture a trading idea to start researching it."
      />
      {error && <p className="mb-4 text-sm text-destructive">{error}</p>}
      <StrategyForm
        submitLabel="Create Strategy"
        isSubmitting={createStrategy.isPending}
        onCancel={() => navigate('/strategies')}
        onSubmit={async (input) => {
          setError(null)
          try {
            const strategy = await createStrategy.mutateAsync(input)
            navigate(`/strategies/${strategy.id}`)
          } catch (err) {
            setError(getErrorMessage(err, 'Unable to create strategy.'))
          }
        }}
      />
    </div>
  )
}
