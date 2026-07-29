import { Pencil, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ErrorState } from '@/components/common/ErrorState'
import { PageHeader } from '@/components/common/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { DeleteStrategyDialog } from '@/features/strategies/components/DeleteStrategyDialog'
import { StrategyCodePanel } from '@/features/strategies/components/StrategyCodePanel'
import { StrategyWorkspaceForm } from '@/features/strategies/components/StrategyWorkspaceForm'
import { useDeleteStrategy, useStrategy, useUpdateStrategy } from '@/features/strategies/queries'
import { priorityMeta } from '@/features/strategies/priorityMeta'
import { statusMeta } from '@/features/strategies/statusMeta'
import type { StrategyUpdateInput } from '@/features/strategies/types'
import { getErrorMessage } from '@/lib/apiClient'
import { formatDate } from '@/lib/format'

function titleCase(value: string): string {
  return `${value[0]?.toUpperCase()}${value.slice(1)}`
}

export default function StrategyDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { data: strategy, isLoading, isError, error, refetch } = useStrategy(id ?? '')
  const updateStrategy = useUpdateStrategy(id ?? '')
  const deleteStrategy = useDeleteStrategy()
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-64" />
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

  const meta = statusMeta(strategy.status)
  const priority = priorityMeta(strategy.priority)
  const tags = strategy.tags
    ? strategy.tags
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean)
    : []

  async function handleSaveResearch(input: StrategyUpdateInput) {
    await updateStrategy.mutateAsync(input)
  }

  return (
    <div>
      <PageHeader
        title={strategy.name}
        description={`${strategy.instrument} · ${strategy.timeframe}`}
        actions={
          <div className="flex items-center gap-2">
            <Button asChild variant="outline">
              <Link to={`/strategies/${strategy.id}/edit`}>
                <Pencil /> Edit
              </Link>
            </Button>
            <Button
              variant="outline"
              className="text-destructive"
              onClick={() => setConfirmingDelete(true)}
            >
              <Trash2 /> Delete
            </Button>
          </div>
        }
      />

      {/* Overview */}
      <Card className="mb-4">
        <CardContent className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <div>
            <p className="text-xs text-muted-foreground">Status</p>
            <Badge className={`mt-1 ${meta.className}`}>{meta.label}</Badge>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Market Type</p>
            <p className="mt-1.5 text-sm">{titleCase(strategy.market_type)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Instrument</p>
            <p className="mt-1.5 text-sm">{strategy.instrument}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Timeframe</p>
            <p className="tabular mt-1.5 text-sm">{strategy.timeframe}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Priority</p>
            <p className={`mt-1.5 text-sm ${priority.className}`}>{titleCase(strategy.priority)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Confidence</p>
            <p className="tabular mt-1.5 text-sm">{strategy.confidence_level} / 10</p>
          </div>
        </CardContent>
      </Card>

      <Card className="mb-4">
        <CardContent className="space-y-4">
          <section>
            <h2 className="text-sm font-medium text-muted-foreground">Description</h2>
            <p className="mt-1 text-sm whitespace-pre-wrap">{strategy.description}</p>
          </section>
          {tags.length > 0 && (
            <section>
              <h2 className="text-sm font-medium text-muted-foreground">Tags</h2>
              <div className="mt-2 flex flex-wrap gap-1">
                {tags.map((tag) => (
                  <Badge key={tag} variant="outline">
                    {tag}
                  </Badge>
                ))}
              </div>
            </section>
          )}
          <section className="flex gap-6 text-xs text-muted-foreground">
            <span>Created {formatDate(strategy.created_at)}</span>
            <span>Updated {formatDate(strategy.updated_at)}</span>
          </section>
        </CardContent>
      </Card>

      <StrategyWorkspaceForm
        strategy={strategy}
        onSave={handleSaveResearch}
        isSaving={updateStrategy.isPending}
      />

      <div className="mt-4">
        <StrategyCodePanel strategyId={strategy.id} />
      </div>

      <DeleteStrategyDialog
        strategy={confirmingDelete ? strategy : null}
        onOpenChange={(open) => !open && setConfirmingDelete(false)}
        onConfirm={() => {
          deleteStrategy.mutate(strategy.id, { onSuccess: () => navigate('/strategies') })
          setConfirmingDelete(false)
        }}
        isDeleting={deleteStrategy.isPending}
      />
    </div>
  )
}
