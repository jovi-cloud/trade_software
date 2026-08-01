import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatInteger, formatNumber, formatPercent } from '@/lib/format'

import {
  computeQualityBreakdown,
  gapDetailRows,
  hasRemovableDatasetIssues,
  sessionIssueRows,
} from '../qualityScore'
import type { PipelineReport } from '../pipelineTypes'
import { useCleanDataset } from '../queries'
import { CleanDatasetPanel } from './CleanDatasetPanel'
import { SessionIssueDetailRow } from './SessionIssueDetailRow'
import { SessionIssuesPieChart } from './SessionIssuesPieChart'

interface QualityScoreBreakdownProps {
  datasetId: string
  pipeline: PipelineReport | null | undefined
  qualityScore: number | null | undefined
  sessionOpen?: string
  sessionClose?: string
  onCleanComplete?: () => void
}

function formatCount(value: number | null, countLabel: string): string {
  if (value === null) return '—'
  if (countLabel === 'gap %') return formatPercent(value, 4)
  return formatInteger(value)
}

export function QualityScoreBreakdownPanel({
  datasetId,
  pipeline,
  qualityScore,
  sessionOpen,
  sessionClose,
  onCleanComplete,
}: QualityScoreBreakdownProps) {
  const [showSessionChart, setShowSessionChart] = useState(false)
  const cleanDataset = useCleanDataset()
  const breakdown = computeQualityBreakdown(pipeline)

  if (!breakdown) {
    return (
      <Card className="mb-4 border-dashed">
        <CardContent className="py-6 text-sm text-muted-foreground">
          Quality score breakdown is not available for this dataset.
        </CardContent>
      </Card>
    )
  }

  const session = pipeline?.session
  const gaps = pipeline?.gaps
  const activeDeductions = breakdown.deductions.filter((item) => item.deduction > 0)
  const showRemovableIssues = hasRemovableDatasetIssues(pipeline)
  const showSessionDetails =
    session !== undefined && sessionIssueRows(session).some((row) => row.count > 0)

  return (
    <Card className="mb-4" id="quality-breakdown">
      <CardHeader>
        <CardTitle className="text-base">Quality score breakdown</CardTitle>
        <p className="text-sm text-muted-foreground">
          Starts at 100 and subtracts capped penalties for each issue found during import.
          Stored score: {qualityScore ?? breakdown.finalScore}.
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-4 font-medium">Factor</th>
                <th className="py-2 pr-4 text-right font-medium">Count</th>
                <th className="py-2 pr-4 font-medium">Formula</th>
                <th className="py-2 pr-4 text-right font-medium">Max</th>
                <th className="py-2 text-right font-medium">Deducted</th>
              </tr>
            </thead>
            <tbody>
              {breakdown.deductions.map((item) => (
                <tr
                  key={item.key}
                  className={`border-b border-border/50 last:border-b-0 ${
                    item.deduction > 0 ? 'text-foreground' : 'text-muted-foreground'
                  }`}
                >
                  <td className="py-2 pr-4">{item.label}</td>
                  <td className="tabular py-2 pr-4 text-right">
                    {formatCount(item.count, item.countLabel)}
                  </td>
                  <td className="py-2 pr-4 font-mono text-xs">{item.formula}</td>
                  <td className="tabular py-2 pr-4 text-right">−{formatNumber(item.maxCap, 0)}</td>
                  <td
                    className={`tabular py-2 text-right font-medium ${
                      item.deduction > 0 ? 'text-loss' : ''
                    }`}
                  >
                    −{formatNumber(item.deduction, 2)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-border font-medium">
                <td className="py-2 pr-4" colSpan={4}>
                  Total deducted
                </td>
                <td className="tabular py-2 text-right text-loss">
                  −{formatNumber(breakdown.totalDeducted, 2)}
                </td>
              </tr>
              <tr className="font-semibold">
                <td className="py-2 pr-4" colSpan={4}>
                  Final score (rounded)
                </td>
                <td className="tabular py-2 text-right">{breakdown.finalScore}</td>
              </tr>
            </tfoot>
          </table>
        </div>

        {activeDeductions.length === 0 && (
          <p className="text-sm text-profit">No penalties applied — perfect import quality.</p>
        )}

        {showRemovableIssues && (
          <CleanDatasetPanel
            datasetId={datasetId}
            pipeline={pipeline}
            sessionOpen={sessionOpen}
            sessionClose={sessionClose}
            isCleaning={cleanDataset.isPending}
            onClean={(input) => {
              cleanDataset.mutate(
                { id: datasetId, input },
                { onSuccess: () => onCleanComplete?.() },
              )
            }}
          />
        )}

        {showSessionDetails && session && (
          <div className="space-y-4">
            <div>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium">Session issue details</p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowSessionChart((open) => !open)}
              >
                {showSessionChart ? 'Hide pie chart' : 'Show pie chart'}
              </Button>
            </div>

            {showSessionChart && (
              <div className="mb-4 rounded-lg border border-border bg-muted/30 p-4">
                <SessionIssuesPieChart session={session} />
              </div>
            )}

            <ul className="space-y-2 text-sm">
              {sessionIssueRows(session)
                .filter((row) => row.count > 0)
                .map((row) => (
                  <SessionIssueDetailRow
                    key={row.key}
                    label={row.label}
                    count={row.count}
                    samples={row.samples}
                    detailNote={
                      row.key === 'missing_opening' || row.key === 'missing_closing'
                        ? 'These are absent bars in the feed, not extra rows. Cleaning cannot remove data gaps.'
                        : undefined
                    }
                    sampleLabel={
                      row.key === 'missing_opening' || row.key === 'missing_closing'
                        ? 'expected bar'
                        : 'sample row'
                    }
                  />
                ))}
            </ul>
            </div>
          </div>
        )}

        {gaps && gapDetailRows(gaps).length > 0 && (
          <div>
            <p className="mb-2 text-sm font-medium">Gap analysis</p>
            <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {gapDetailRows(gaps).map((row) => (
                <div key={row.label}>
                  <dt className="text-xs text-muted-foreground">{row.label}</dt>
                  <dd className="tabular mt-1 text-sm font-medium">
                    {typeof row.count === 'number' && row.label === 'Gap %'
                      ? formatPercent(row.count)
                      : formatInteger(
                          typeof row.count === 'number' ? row.count : Number(row.count),
                        )}
                  </dd>
                </div>
              ))}
            </dl>
            {gaps.missing_details && gaps.missing_details.length > 0 && (
              <ul className="mt-3 max-h-48 space-y-1 overflow-y-auto text-xs text-muted-foreground">
                {gaps.missing_details.slice(0, 20).map((detail) => (
                  <li key={detail} className="tabular">
                    {detail}
                  </li>
                ))}
                {gaps.missing_details.length > 20 && (
                  <li>…and {gaps.missing_details.length - 20} more</li>
                )}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
