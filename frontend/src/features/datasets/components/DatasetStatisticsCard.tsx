import { ChevronDown, ChevronUp } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate, formatInteger, formatNumber, formatPercent } from '@/lib/format'

import type { Dataset } from '../types'
import type { PipelineReport } from '../pipelineTypes'

interface DatasetStatisticsCardProps {
  dataset: Dataset
  showQualityBreakdown: boolean
  onToggleQualityBreakdown: () => void
}

export function DatasetStatisticsCard({
  dataset,
  showQualityBreakdown,
  onToggleQualityBreakdown,
}: DatasetStatisticsCardProps) {
  const pipeline = (dataset as Dataset & { pipeline_report?: PipelineReport | null })
    .pipeline_report
  const stats = pipeline?.statistics

  if (!stats) return null

  const qualityScore =
    (dataset as Dataset & { quality_score?: number | null }).quality_score ??
    pipeline?.quality_score ??
    stats.quality_score

  return (
    <Card className="mb-4">
      <CardHeader>
        <CardTitle className="text-base">Dataset statistics</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-xs text-muted-foreground">Instrument</dt>
            <dd className="mt-1 text-sm font-medium">{stats.instrument}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Timeframe</dt>
            <dd className="mt-1 text-sm font-medium">{stats.timeframe ?? dataset.timeframe}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Total bars</dt>
            <dd className="tabular mt-1 text-sm font-medium">{formatInteger(stats.total_bars)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Trading days</dt>
            <dd className="tabular mt-1 text-sm font-medium">{formatInteger(stats.trading_days)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Avg bars / day</dt>
            <dd className="tabular mt-1 text-sm font-medium">
              {formatNumber(stats.average_daily_bars, 1)}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Price range</dt>
            <dd className="tabular mt-1 text-sm font-medium">
              {stats.min_price !== null && stats.max_price !== null
                ? `${formatNumber(stats.min_price, 2)} – ${formatNumber(stats.max_price, 2)}`
                : '—'}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Avg volume</dt>
            <dd className="tabular mt-1 text-sm font-medium">
              {stats.average_volume !== null ? formatInteger(stats.average_volume) : '—'}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Fingerprint</dt>
            <dd className="mt-1 truncate font-mono text-xs">{dataset.file_hash ?? '—'}</dd>
          </div>
          {stats.date_range_start && stats.date_range_end && (
            <div className="sm:col-span-2">
              <dt className="text-xs text-muted-foreground">Coverage</dt>
              <dd className="tabular mt-1 text-sm">
                {formatDate(stats.date_range_start)} → {formatDate(stats.date_range_end)}
              </dd>
            </div>
          )}
          <div>
            <dt className="text-xs text-muted-foreground">Gap %</dt>
            <dd className="tabular mt-1 text-sm">{formatPercent(stats.gap_percentage)}</dd>
          </div>
          <div>
            <dt className="text-xs text-muted-foreground">Quality score</dt>
            <dd className="mt-1">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="tabular h-auto px-0 text-sm font-medium hover:bg-transparent"
                onClick={onToggleQualityBreakdown}
              >
                {qualityScore ?? '—'}
                {showQualityBreakdown ? (
                  <ChevronUp className="size-4" />
                ) : (
                  <ChevronDown className="size-4" />
                )}
              </Button>
              <p className="text-xs text-muted-foreground">Click to see how this was calculated</p>
            </dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  )
}
