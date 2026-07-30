import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate, formatInteger, formatPercent } from '@/lib/format'

import type { Dataset } from '../types'

interface CheckRowProps {
  label: string
  count: number
  zeroIsGood: boolean
  samples?: readonly string[]
}

function CheckRow({ label, count, zeroIsGood, samples }: CheckRowProps) {
  const isGood = zeroIsGood ? count === 0 : count > 0
  const Icon = isGood ? CheckCircle2 : AlertTriangle

  return (
    <div className="flex items-start justify-between gap-4 border-b border-border py-2 last:border-b-0">
      <div className="flex min-w-0 items-start gap-2">
        <Icon className={`mt-0.5 size-4 shrink-0 ${isGood ? 'text-profit' : 'text-loss'}`} />
        <div className="min-w-0">
          <p className="text-sm">{label}</p>
          {samples && samples.length > 0 && (
            <ul className="mt-1 space-y-0.5">
              {samples.slice(0, 5).map((sample) => (
                <li key={sample} className="tabular truncate text-xs text-muted-foreground">
                  {sample}
                </li>
              ))}
              {samples.length > 5 && (
                <li className="text-xs text-muted-foreground">…and {samples.length - 5} more</li>
              )}
            </ul>
          )}
        </div>
      </div>
      <span className={`tabular shrink-0 text-sm font-medium ${isGood ? '' : 'text-loss'}`}>
        {formatInteger(count)}
      </span>
    </div>
  )
}

interface ValidationReportCardProps {
  dataset: Dataset
}

export function ValidationReportCard({ dataset }: ValidationReportCardProps) {
  const report = dataset.validation_report
  const pipeline = (dataset as Dataset & { pipeline_report?: PipelineReport }).pipeline_report
  const qualityScore =
    (dataset as Dataset & { quality_score?: number | null }).quality_score ??
    pipeline?.quality_score

  if (!report) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Validation Report</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-start gap-2">
            <XCircle className="mt-0.5 size-4 shrink-0 text-loss" />
            <div>
              <p className="text-sm">
                {dataset.import_error ??
                  (dataset.import_status === 'failed'
                    ? 'This import failed before validation could run.'
                    : 'No validation report is available for this dataset yet.')}
              </p>
              {pipeline?.rejection_reason && (
                <p className="mt-1 text-xs text-muted-foreground">{pipeline.rejection_reason}</p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  const gaps = pipeline?.gaps

  return (
    <Card>
      <CardHeader>
        <CardTitle>Validation Report</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-4">
          <div>
            <p className="text-xs text-muted-foreground">Quality score</p>
            <p
              className={`tabular mt-1 text-lg font-semibold ${
                qualityScore !== null && qualityScore !== undefined && qualityScore >= 80
                  ? 'text-profit'
                  : qualityScore !== null && qualityScore !== undefined && qualityScore >= 70
                    ? 'text-yellow-500'
                    : 'text-loss'
              }`}
            >
              {qualityScore ?? '--'}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Total rows read</p>
            <p className="tabular mt-1 text-lg font-semibold">{formatInteger(report.total_rows)}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Valid rows</p>
            <p className="tabular mt-1 text-lg font-semibold text-profit">
              {formatInteger(report.valid_rows)}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground">Date range</p>
            <p className="tabular mt-1 text-sm">
              {report.start_date && report.end_date
                ? `${formatDate(report.start_date)} → ${formatDate(report.end_date)}`
                : '--'}
            </p>
          </div>
        </div>

        {gaps && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              <strong className="font-medium text-foreground">Missing bars</strong> counts timestamps
              where the gap between consecutive bars is longer than one bar interval (e.g. 5
              minutes). Overnight closes, weekends, and holidays are included in this total for
              intraday data — so a jump like Friday 15:25 → Monday 09:15 is expected, not a CSV
              error. Worry about gaps that fall inside a trading session.
            </p>
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <p className="text-xs text-muted-foreground">Missing bars</p>
                <p className="tabular mt-1 text-sm">{formatInteger(gaps.missing_bars)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Gap %</p>
                <p className="tabular mt-1 text-sm">{formatPercent(gaps.gap_percentage)}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Detected timeframe</p>
                <p className="tabular mt-1 text-sm">
                  {(dataset as Dataset & { detected_timeframe?: string | null }).detected_timeframe ??
                    pipeline?.timeframe?.detected ??
                    dataset.timeframe}
                </p>
              </div>
            </div>
          </div>
        )}

        <div>
          <CheckRow label="Valid rows" count={report.valid_rows} zeroIsGood={false} />
          <CheckRow label="Invalid dates" count={report.invalid_dates} zeroIsGood />
          <CheckRow label="Invalid prices" count={report.invalid_prices} zeroIsGood />
          <CheckRow
            label="OHLC violations"
            count={(report as DatasetValidationReportExtended).ohlc_violations ?? 0}
            zeroIsGood
          />
          <CheckRow
            label="Duplicate timestamps"
            count={report.duplicate_timestamps}
            zeroIsGood
            samples={report.duplicate_samples ?? undefined}
          />
          <CheckRow
            label="Missing bars"
            count={report.missing_timestamps}
            zeroIsGood
            samples={report.gap_samples ?? undefined}
          />
        </div>

        {pipeline?.cleaning?.actions && pipeline.cleaning.actions.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">Cleaning actions</p>
            <ul className="space-y-1 text-xs text-muted-foreground">
              {pipeline.cleaning.actions.map((action) => (
                <li key={action.action}>
                  {action.action}: {formatInteger(action.count)}
                  {action.detail ? ` (${action.detail})` : ''}
                </li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

interface DatasetValidationReportExtended {
  ohlc_violations?: number
}

interface PipelineReport {
  quality_score: number
  rejected?: boolean
  rejection_reason?: string | null
  gaps?: { missing_bars: number; gap_percentage: number }
  timeframe?: { detected?: string | null }
  cleaning?: { actions: { action: string; count: number; detail?: string }[] }
}
