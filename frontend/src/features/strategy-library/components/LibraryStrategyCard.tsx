import { Play, Star } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'

import { categoryLabel, riskClassName, riskLabel } from '../categoryMeta'
import type { LibraryStrategyListItem } from '../types'

interface LibraryStrategyCardProps {
  strategy: LibraryStrategyListItem
  isFavorite?: boolean
}

export function LibraryStrategyCard({ strategy, isFavorite }: LibraryStrategyCardProps) {
  return (
    <Card className="gap-3 py-5">
      <CardHeader className="grid-rows-1 gap-2 px-5">
        <div className="flex items-start justify-between gap-2">
          <Link to={`/strategy-library/${strategy.id}`} className="min-w-0">
            <h3 className="truncate text-sm font-semibold hover:underline">{strategy.name}</h3>
          </Link>
          {isFavorite && (
            <Star
              className="size-4 shrink-0 fill-amber-400 text-amber-400"
              aria-label="Favourite"
            />
          )}
        </div>
        <div className="flex flex-wrap gap-1.5">
          <Badge variant="secondary">{categoryLabel(strategy.category)}</Badge>
          <Badge className={riskClassName(strategy.risk_level)}>
            {riskLabel(strategy.risk_level)}
          </Badge>
          {!strategy.is_valid && <Badge variant="destructive">Invalid</Badge>}
        </div>
      </CardHeader>
      <CardContent className="space-y-3 px-5">
        <p className="line-clamp-3 text-sm text-muted-foreground">{strategy.description}</p>
        <div className="flex flex-wrap gap-1">
          {strategy.tags.slice(0, 4).map((tag) => (
            <Badge key={tag} variant="outline" className="text-xs">
              {tag}
            </Badge>
          ))}
        </div>
        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span>v{strategy.version}</span>
          <span>{strategy.direction}</span>
          <span>{strategy.parameter_count} parameters</span>
        </div>
        <div className="flex items-center gap-2 pt-1">
          <Button size="sm" variant="outline" asChild>
            <Link to={`/strategy-library/${strategy.id}`}>Details</Link>
          </Button>
          <Button size="sm" disabled={!strategy.is_valid} asChild={strategy.is_valid}>
            {strategy.is_valid ? (
              <Link to={`/backtests?library=${strategy.id}`}>
                <Play className="size-4" />
                Run
              </Link>
            ) : (
              <span>
                <Play className="size-4" />
                Run
              </span>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
