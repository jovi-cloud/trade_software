import { MoreVertical, Trash2 } from 'lucide-react'
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
import { formatDate, formatInteger } from '@/lib/format'

import { importStatusMeta } from '../importStatusMeta'
import type { Dataset } from '../types'

interface DatasetCardProps {
  dataset: Dataset
  onDeleteRequest: (dataset: Dataset) => void
}

export function DatasetCard({ dataset, onDeleteRequest }: DatasetCardProps) {
  const meta = importStatusMeta(dataset.import_status)

  return (
    <Card className="gap-3 py-5">
      <CardHeader className="grid-rows-1 gap-2 px-5">
        <div className="flex items-start justify-between gap-2">
          <Link to={`/data/${dataset.id}`} className="min-w-0">
            <h3 className="truncate text-sm font-semibold hover:underline">{dataset.name}</h3>
          </Link>
          <div className="flex shrink-0 items-center gap-1.5">
            <Badge className={meta.className}>{meta.label}</Badge>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon-sm" aria-label="Dataset actions">
                  <MoreVertical className="size-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem variant="destructive" onSelect={() => onDeleteRequest(dataset)}>
                  <Trash2 /> Delete
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span>{dataset.symbol}</span>
          <span aria-hidden>·</span>
          <span>{dataset.exchange}</span>
          <span aria-hidden>·</span>
          <span className="tabular">{dataset.timeframe}</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 px-5">
        <div className="flex items-baseline gap-1.5">
          <span className="tabular text-lg font-semibold">{formatInteger(dataset.row_count)}</span>
          <span className="text-xs text-muted-foreground">bars</span>
        </div>
        <p className="tabular text-xs text-muted-foreground">
          {dataset.start_date && dataset.end_date
            ? `${formatDate(dataset.start_date)} → ${formatDate(dataset.end_date)}`
            : 'No date range'}
        </p>
        <p className="text-xs text-muted-foreground">Imported {formatDate(dataset.created_at)}</p>
      </CardContent>
    </Card>
  )
}
