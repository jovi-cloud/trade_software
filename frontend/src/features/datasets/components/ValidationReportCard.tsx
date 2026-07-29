import { AlertTriangle, CheckCircle2, XCircle } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate, formatInteger } from '@/lib/format'

import type { Dataset } from '../types'

interface CheckRowProps {
  label: string
  count: number
  /** A count of zero is the good outcome for problem rows, but not for valid rows. */
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
              {dataset.import_status === 'failed' && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Fix the CSV and import it again.
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Validation Report</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-3">
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

        <div>
          <CheckRow label="Valid rows" count={report.valid_rows} zeroIsGood={false} />
          <CheckRow label="Invalid dates" count={report.invalid_dates} zeroIsGood />
          <CheckRow label="Invalid prices" count={report.invalid_prices} zeroIsGood />
          <CheckRow
            label="Duplicate timestamps"
            count={report.duplicate_timestamps}
            zeroIsGood
            samples={report.duplicate_samples ?? undefined}
          />
          <CheckRow
            label="Missing timestamps"
            count={report.missing_timestamps}
            zeroIsGood
            samples={report.gap_samples ?? undefined}
          />
        </div>

        {report.missing_timestamps > 0 && (
          <p className="text-xs text-muted-foreground">
            Missing bars are counted against a naive {dataset.timeframe} calendar, so normal
            weekends, holidays and session breaks are included in this number.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
