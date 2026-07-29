import { MoreVertical, Pencil, Trash2 } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { formatDate } from '@/lib/format'

import { priorityMeta } from '../priorityMeta'
import { statusMeta } from '../statusMeta'
import type { Strategy } from '../types'

interface StrategyCardProps {
  strategy: Strategy
  onDeleteRequest: (strategy: Strategy) => void
}

export function StrategyCard({ strategy, onDeleteRequest }: StrategyCardProps) {
  const meta = statusMeta(strategy.status)
  const priority = priorityMeta(strategy.priority)
  const tags = strategy.tags
    ? strategy.tags
        .split(',')
        .map((tag) => tag.trim())
        .filter(Boolean)
    : []

  return (
    <Card className="gap-3 py-5">
      <CardHeader className="grid-rows-1 gap-2 px-5">
        <div className="flex items-start justify-between gap-2">
          <Link to={`/strategies/${strategy.id}`} className="min-w-0">
            <h3 className="truncate text-sm font-semibold hover:underline">{strategy.name}</h3>
          </Link>
          <div className="flex shrink-0 items-center gap-1.5">
            <Badge className={meta.className}>{meta.label}</Badge>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon-sm" aria-label="Strategy actions">
                  <MoreVertical className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem asChild>
                  <Link to={`/strategies/${strategy.id}/edit`}>
                    <Pencil /> Edit
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem variant="destructive" onSelect={() => onDeleteRequest(strategy)}>
                  <Trash2 /> Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span>{strategy.instrument}</span>
          <span aria-hidden>·</span>
          <span className="tabular">{strategy.timeframe}</span>
          <span aria-hidden>·</span>
          <span className={priority.className}>{priority.label}</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 px-5">
        <p className="line-clamp-2 text-sm text-muted-foreground">{strategy.description}</p>
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {tags.map((tag) => (
              <Badge key={tag} variant="outline" className="font-normal text-muted-foreground">
                {tag}
              </Badge>
            ))}
          </div>
        )}
        <p className="text-xs text-muted-foreground">Updated {formatDate(strategy.updated_at)}</p>
      </CardContent>
    </Card>
  )
}
