import { ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'

import { formatInteger } from '@/lib/format'

interface SessionIssueDetailRowProps {
  label: string
  count: number
  samples?: readonly string[]
  emptyDetailMessage?: string
  detailNote?: string
  sampleLabel?: string
}

export function SessionIssueDetailRow({
  label,
  count,
  samples,
  emptyDetailMessage = 'No row-level samples are stored for this version. Re-validate the dataset to refresh details.',
  detailNote,
  sampleLabel = 'sample row',
}: SessionIssueDetailRowProps) {
  const [expanded, setExpanded] = useState(false)
  const canExpand = count > 0

  return (
    <li className="rounded-md border border-border/60 bg-background">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-4 px-3 py-2 text-left text-sm disabled:cursor-default"
        disabled={!canExpand}
        onClick={() => canExpand && setExpanded((open) => !open)}
      >
        <span className="flex min-w-0 items-center gap-2">
          {canExpand && (
            expanded ? (
              <ChevronUp className="size-4 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronDown className="size-4 shrink-0 text-muted-foreground" />
            )
          )}
          <span>{label}</span>
        </span>
        <span className="tabular shrink-0 font-medium text-loss">{formatInteger(count)}</span>
      </button>

      {expanded && canExpand && (
        <div className="border-t border-border/60 px-3 py-2">
          {detailNote && (
            <p className="mb-2 text-xs text-muted-foreground">{detailNote}</p>
          )}
          {samples && samples.length > 0 ? (
            <>
              <p className="mb-2 text-xs text-muted-foreground">
                Showing {formatInteger(samples.length)} {sampleLabel}
                {samples.length === 1 ? '' : 's'}
                {count > samples.length
                  ? ` of ${formatInteger(count)} total (first ${formatInteger(samples.length)} stored)`
                  : ''}
              </p>
              <ul className="max-h-48 space-y-1 overflow-y-auto text-xs">
                {samples.map((sample) => (
                  <li key={sample} className="tabular rounded bg-muted/40 px-2 py-1">
                    {sample}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-xs text-muted-foreground">{emptyDetailMessage}</p>
          )}
        </div>
      )}
    </li>
  )
}
