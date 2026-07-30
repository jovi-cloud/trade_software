import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatNumber, formatTimestamp } from '@/lib/format'

import { DECISION_PAGE_SIZE, useDecisions } from '@/features/explain/queries'
import type { DecisionRow, DecisionSchema } from '@/features/explain/api'

interface DecisionLogTableProps {
  runId: string
  totalRows: number
  onSelectBar?: (barIndex: number) => void
}

/**
 * Every bar of the run as one scrollable table: OHLC, every indicator value,
 * every condition verdict, every operand.
 *
 * Paged rather than virtualised-over-everything because the log is uncapped — a
 * 194,553-bar run is ~6 MB on disk and reading it whole to render a hundred rows
 * would reintroduce the memory problem the columnar format removed.
 */
export function DecisionLogTable({ runId, totalRows, onSelectBar }: DecisionLogTableProps) {
  const [start, setStart] = useState(0)
  const [onlyDecisions, setOnlyDecisions] = useState(false)
  const { data, isPending, isError, error } = useDecisions(runId, start)

  if (isPending) {
    return <p className="text-sm text-muted-foreground">Loading decision log…</p>
  }
  if (isError) {
    return (
      <p className="text-sm text-destructive">
        {error instanceof Error ? error.message : 'Could not load the decision log.'}
      </p>
    )
  }

  const schema = data.log_schema
  const rows = onlyDecisions ? data.rows.filter((row) => hasVerdict(row)) : data.rows
  const last = Math.max(0, totalRows - DECISION_PAGE_SIZE)
  const windowEnd = Math.min(start + DECISION_PAGE_SIZE, totalRows)

  return (
    <Card>
      <CardHeader className="gap-3">
        <CardTitle className="text-base">
          Decision log
          <span className="ml-2 font-normal text-muted-foreground">
            bars {start.toLocaleString()}–{windowEnd.toLocaleString()} of{' '}
            {totalRows.toLocaleString()}
          </span>
        </CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={() => setStart(0)}
            disabled={start === 0}
          >
            First
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setStart(Math.max(0, start - DECISION_PAGE_SIZE))}
            disabled={start === 0}
          >
            Previous
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setStart(Math.min(last, start + DECISION_PAGE_SIZE))}
            disabled={start >= last}
          >
            Next
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setStart(last)}
            disabled={start >= last}
          >
            Last
          </Button>
          <label className="ml-2 flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={onlyDecisions}
              onChange={(event) => setOnlyDecisions(event.target.checked)}
              className="h-4 w-4 rounded border-border"
            />
            Only bars where a rule was evaluated
          </label>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-left text-xs">
            <thead className="bg-muted/40 text-muted-foreground">
              <tr>
                <th className="whitespace-nowrap px-2 py-2 font-medium">Bar</th>
                <th className="whitespace-nowrap px-2 py-2 font-medium">Time</th>
                <th className="whitespace-nowrap px-2 py-2 text-right font-medium">Close</th>
                {schema.indicators?.map((name) => (
                  <th key={name} className="whitespace-nowrap px-2 py-2 text-right font-medium">
                    {name}
                  </th>
                ))}
                {schema.conditions?.map((condition) => (
                  <th
                    key={condition.name}
                    className="whitespace-nowrap px-2 py-2 text-center font-medium"
                    title={`Expected: ${condition.expected}`}
                  >
                    {abbreviate(condition.name)}
                  </th>
                ))}
                {schema.operands?.map((operand) => (
                  <th
                    key={operand.name}
                    className="whitespace-nowrap px-2 py-2 text-right font-medium"
                    title={operand.label}
                  >
                    {abbreviate(operand.label)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="font-mono tabular-nums">
              {rows.map((row) => (
                <tr
                  key={row.bar_index}
                  className="border-t border-border hover:bg-muted/30"
                  onClick={() => onSelectBar?.(row.bar_index)}
                >
                  <td className="px-2 py-1">
                    {onSelectBar ? (
                      <button type="button" className="underline-offset-2 hover:underline">
                        {row.bar_index.toLocaleString()}
                      </button>
                    ) : (
                      row.bar_index.toLocaleString()
                    )}
                  </td>
                  <td className="whitespace-nowrap px-2 py-1 text-muted-foreground">
                    {formatTimestamp(row.ts)}
                  </td>
                  <td className="px-2 py-1 text-right">{formatNumber(row.close)}</td>
                  {schema.indicators?.map((name) => (
                    <td key={name} className="px-2 py-1 text-right">
                      {cell(row.indicators?.[name])}
                    </td>
                  ))}
                  {schema.conditions?.map((condition) => (
                    <td key={condition.name} className="px-2 py-1 text-center">
                      <Verdict value={row.conditions?.[condition.name]} />
                    </td>
                  ))}
                  {schema.operands?.map((operand) => (
                    <td key={operand.name} className="px-2 py-1 text-right">
                      {cell(findOperand(row, operand.name))}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">✓</span> passed ·{' '}
          <span className="font-medium text-destructive">✕</span> failed ·{' '}
          <span className="font-medium">·</span> not reached on this bar. Hover a column heading for
          its full name and expected value.
        </p>
      </CardContent>
    </Card>
  )
}

function Verdict({ value }: { value: boolean | null | undefined }) {
  // Three states, three glyphs. Collapsing "not reached" into "failed" is what
  // made a rule below an earlier gate look like the rule that was blocking.
  if (value === null || value === undefined) {
    return <span className="text-muted-foreground/50">·</span>
  }
  return value ? (
    <span className="text-foreground">✓</span>
  ) : (
    <span className="text-destructive">✕</span>
  )
}

function hasVerdict(row: DecisionRow): boolean {
  return Object.values(row.conditions ?? {}).some((value) => value !== null && value !== undefined)
}

function findOperand(row: DecisionRow, name: string): number | undefined {
  return row.operands?.find((operand) => operand.name === name)?.value
}

function cell(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  const digits = Math.abs(value) > 0 && Math.abs(value) < 1 ? 6 : 2
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })
}

/** Column headings have to fit; the full text is on the `title` attribute. */
function abbreviate(label: string): string {
  const words = label.split(/\s+/)
  if (label.length <= 14 || words.length < 3) return label
  return words.map((word) => word[0]?.toUpperCase() ?? '').join('')
}

export type { DecisionSchema }
