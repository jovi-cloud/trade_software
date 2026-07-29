import { Plus } from 'lucide-react'
import { Link } from 'react-router-dom'

import { EmptyState } from '@/components/common/EmptyState'
import { ErrorState } from '@/components/common/ErrorState'
import { PageHeader } from '@/components/common/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useStrategyStats } from '@/features/strategies/queries'
import { statusMeta } from '@/features/strategies/statusMeta'
import type { Strategy, StrategyStats } from '@/features/strategies/types'
import { getErrorMessage } from '@/lib/apiClient'
import { formatDate } from '@/lib/format'

const STAT_TILES = [
  { key: 'total', label: 'Total strategies' },
  { key: 'draft', label: 'Draft' },
  { key: 'testing', label: 'Testing' },
  { key: 'validated', label: 'Validated' },
] as const

interface StrategyListCardProps {
  title: string
  description: string
  strategies: Strategy[]
  emptyMessage: string
}

function StrategyListCard({ title, description, strategies, emptyMessage }: StrategyListCardProps) {
  return (
    <Card>
      <CardHeader>
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </CardHeader>
      <CardContent>
        {strategies.length === 0 ? (
          <p className="text-sm text-muted-foreground">{emptyMessage}</p>
        ) : (
          <ul className="divide-y divide-border">
            {strategies.map((strategy) => {
              const meta = statusMeta(strategy.status)
              return (
                <li key={strategy.id} className="py-3 first:pt-0 last:pb-0">
                  <Link
                    to={`/strategies/${strategy.id}`}
                    className="flex items-center justify-between gap-4"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium hover:underline">
                        {strategy.name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {strategy.instrument} · {strategy.timeframe}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <Badge className={meta.className}>{meta.label}</Badge>
                      <span className="text-xs text-muted-foreground">
                        {formatDate(strategy.updated_at)}
                      </span>
                    </div>
                  </Link>
                </li>
              )
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

function StrategyLists({ stats }: { stats: StrategyStats }) {
  return (
    <div className="mt-4 grid gap-4 lg:grid-cols-3">
      <StrategyListCard
        title="High Priority Strategies"
        description="Ideas flagged as high priority."
        strategies={stats.high_priority}
        emptyMessage="No high priority strategies right now."
      />
      <StrategyListCard
        title="Recent Research"
        description="Most recently updated strategies."
        strategies={stats.recent_research}
        emptyMessage="Nothing updated yet."
      />
      <StrategyListCard
        title="Strategies Needing Review"
        description="In testing, waiting the longest for a decision."
        strategies={stats.needs_review}
        emptyMessage="Nothing is in testing right now."
      />
    </div>
  )
}

export default function DashboardPage() {
  const { data: stats, isLoading, isError, error, refetch } = useStrategyStats()

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Where your research loop stands right now."
        actions={
          <Button asChild>
            <Link to="/strategies/new">
              <Plus /> New Strategy
            </Link>
          </Button>
        }
      />

      {isLoading && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {STAT_TILES.map((tile) => (
            <Skeleton key={tile.key} className="h-24" />
          ))}
        </div>
      )}

      {isError && (
        <ErrorState
          message={getErrorMessage(error, 'Unable to load dashboard stats.')}
          onRetry={() => refetch()}
        />
      )}

      {!isLoading && !isError && stats && stats.total === 0 && (
        <EmptyState
          title="No strategies yet"
          description="Create your first strategy idea to start the research loop."
          action={
            <Button asChild>
              <Link to="/strategies/new">
                <Plus /> New Strategy
              </Link>
            </Button>
          }
        />
      )}

      {!isLoading && !isError && stats && stats.total > 0 && (
        <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {STAT_TILES.map((tile) => (
              <Card key={tile.key}>
                <CardContent>
                  <p className="text-sm text-muted-foreground">{tile.label}</p>
                  <p className="mt-1 text-3xl font-semibold">{stats[tile.key]}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          <StrategyLists stats={stats} />
        </>
      )}
    </div>
  )
}
