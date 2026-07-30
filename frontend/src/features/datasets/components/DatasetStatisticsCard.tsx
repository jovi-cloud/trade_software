import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate, formatInteger, formatNumber, formatPercent } from '@/lib/format'

import type { Dataset } from '../types'

interface PipelineStatistics {
  total_bars: number
  trading_days: number
  average_daily_bars: number
  min_price: number | null
  max_price: number | null
  average_volume: number | null
  instrument: string
  missing_bars: number
  duplicate_bars: number
  gap_percentage: number
  quality_score: number
  date_range_start?: string | null
  date_range_end?: string | null
  timeframe?: string | null
}

interface DatasetStatisticsCardProps {
  dataset: Dataset
}

export function DatasetStatisticsCard({ dataset }: DatasetStatisticsCardProps) {
  const stats = (
    dataset as Dataset & {
      pipeline_report?: { statistics?: PipelineStatistics | null }
    }
  ).pipeline_report?.statistics

  if (!stats) return null

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
            <dd className="tabular mt-1 text-sm font-medium">{stats.quality_score}</dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  )
}
