import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate, formatInteger, formatPercent } from '@/lib/format'

import { sessionIssueRows, priceAnomalyRows } from '../qualityScore'
import type { PipelineReport } from '../pipelineTypes'
import type { Dataset } from '../types'
import { SessionIssueDetailRow } from './SessionIssueDetailRow'

const GAP_DETAIL_NOTE =
  'These are absent bars in the feed, not extra rows. Cleaning cannot remove data gaps — re-validate after re-import or accept partial trading days.'

function sessionDetailProps(row: ReturnType<typeof sessionIssueRows>[number]) {
  const isGap = row.key === 'missing_opening' || row.key === 'missing_closing'
  return {
    samples: row.samples,
    expandable: row.count > 0,
    detailNote: isGap ? GAP_DETAIL_NOTE : undefined,
    sampleLabel: isGap ? 'expected bar' : 'sample row',
  }
}

interface CheckRowProps {
  label: string
  count: number
  zeroIsGood: boolean
  samples?: readonly string[]
  expandable?: boolean
  detailNote?: string
  sampleLabel?: string
}

function CheckRow({
  label,
  count,
  zeroIsGood,
  samples,
  expandable = false,
  detailNote,
  sampleLabel,
}: CheckRowProps) {
  if (expandable && count > 0) {
    return (
      <div className="border-b border-border py-2 last:border-b-0">
        <SessionIssueDetailRow
          label={label}
          count={count}
          samples={samples}
          detailNote={detailNote}
          sampleLabel={sampleLabel}
        />
      </div>
    )
  }

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
  onShowQualityBreakdown?: () => void
}

export function ValidationReportCard({
  dataset,
  onShowQualityBreakdown,
}: ValidationReportCardProps) {
  const report = dataset.validation_report
  const pipeline = (dataset as Dataset & { pipeline_report?: PipelineReport | null })
    .pipeline_report
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
  const session = pipeline?.session
  const priceAnomalies = pipeline?.price_anomalies
  const anomalyRows = priceAnomalyRows(priceAnomalies)

  return (
    <Card className="mb-4">
      <CardHeader>
        <CardTitle>Validation Report</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-4">
          <div>
            <p className="text-xs text-muted-foreground">Quality score</p>
            <div className="mt-1 flex items-center gap-2">
              <p
                className={`tabular text-lg font-semibold ${
                  qualityScore !== null && qualityScore !== undefined && qualityScore >= 80
                    ? 'text-profit'
                    : qualityScore !== null && qualityScore !== undefined && qualityScore >= 70
                      ? 'text-yellow-500'
                      : 'text-loss'
                }`}
              >
                {qualityScore ?? '--'}
              </p>
              {onShowQualityBreakdown && (
                <Button type="button" variant="link" size="sm" onClick={onShowQualityBreakdown}>
                  How calculated?
                </Button>
              )}
            </div>
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
                ? `${formatDate(report.start_date, dataset.timezone)} → ${formatDate(report.end_date, dataset.timezone)}`
                : '--'}
            </p>
          </div>
        </div>

        {gaps && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              <strong className="font-medium text-foreground">Missing bars</strong> counts only
              gaps inside a trading session (default 09:15–15:25 last bar open in the dataset&apos;s
              exchange timezone). Overnight closes, weekends, holidays, and full non-trading days
              are ignored.
            </p>
            <div className="grid gap-4 sm:grid-cols-3">
              <div>
                <p className="text-xs text-muted-foreground">Intraday missing bars</p>
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
            {gaps.missing_details && gaps.missing_details.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-medium text-muted-foreground">
                  Missing bar details
                </p>
                <ul className="max-h-48 space-y-1 overflow-y-auto text-xs text-muted-foreground">
                  {gaps.missing_details.slice(0, 20).map((detail) => (
                    <li key={detail} className="tabular">
                      {detail}
                    </li>
                  ))}
                  {gaps.missing_details.length > 20 && (
                    <li>…and {gaps.missing_details.length - 20} more (see import logs)</li>
                  )}
                </ul>
              </div>
            )}
          </div>
        )}

        <div>
          <CheckRow label="Valid rows" count={report.valid_rows} zeroIsGood={false} />
          <CheckRow label="Invalid dates" count={report.invalid_dates} zeroIsGood />
          <CheckRow label="Invalid prices" count={report.invalid_prices} zeroIsGood />
          <CheckRow label="OHLC violations" count={report.ohlc_violations} zeroIsGood />
          <CheckRow
            label="Negative volumes"
            count={report.negative_volumes}
            zeroIsGood
          />
          <CheckRow
            label="Non-positive prices"
            count={report.non_positive_prices}
            zeroIsGood
          />
          <CheckRow label="NaN values" count={report.nan_values} zeroIsGood />
          <CheckRow label="Infinity values" count={report.infinity_values} zeroIsGood />
          <CheckRow
            label="Duplicate timestamps"
            count={report.duplicate_timestamps}
            zeroIsGood
            samples={report.duplicate_samples ?? undefined}
          />
          <CheckRow
            label="Out-of-order timestamps"
            count={report.out_of_order_timestamps}
            zeroIsGood
          />
          <CheckRow
            label="Intraday missing bars"
            count={gaps?.missing_bars ?? report.missing_timestamps}
            zeroIsGood
            samples={gaps?.missing_timestamps ?? report.gap_samples ?? undefined}
          />
        </div>

        {anomalyRows.some((row) => row.count > 0) && (
          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">
              Price anomaly checks (intraday bars and consecutive trading days)
            </p>
            {anomalyRows.map((row) => (
              <CheckRow
                key={row.key}
                label={row.label}
                count={row.count}
                zeroIsGood
                samples={row.samples}
                expandable={row.count > 0}
                detailNote={
                  row.dayCount > 0
                    ? `${formatInteger(row.dayCount)} trading day(s) affected: ${row.daySamples?.join(', ')}`
                    : undefined
                }
                sampleLabel="spike"
              />
            ))}
          </div>
        )}

        {session && sessionIssueRows(session).some((row) => row.count > 0) && (
          <div>
            <p className="mb-2 text-xs font-medium text-muted-foreground">Session checks</p>
            {sessionIssueRows(session).map((row) => {
              const detail = sessionDetailProps(row)
              return (
                <CheckRow
                  key={row.key}
                  label={row.label}
                  count={row.count}
                  zeroIsGood
                  samples={detail.samples}
                  expandable={detail.expandable}
                  detailNote={detail.detailNote}
                  sampleLabel={detail.sampleLabel}
                />
              )
            })}
          </div>
        )}

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
