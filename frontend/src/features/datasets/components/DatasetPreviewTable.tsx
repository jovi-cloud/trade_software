import { useState } from 'react'

import { ErrorState } from '@/components/common/ErrorState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { getErrorMessage } from '@/lib/apiClient'
import { formatInteger, formatNumber, formatTimestamp } from '@/lib/format'

import { useDatasetBars, useDatasetPreview } from '../queries'
import type { PreviewPart } from '../types'

const PREVIEW_ROWS = 20
const BROWSE_PAGE_SIZE = 100

type ViewMode = 'preview' | 'browse'

interface DatasetPreviewTableProps {
  datasetId: string
  totalBars: number
  timezone?: string
}

function BarsTable({
  rows,
  timezone,
}: {
  rows: Array<{ ts: number; open: number; high: number; low: number; close: number; volume: number }>
  timezone?: string
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="py-2 pr-4 font-medium">Timestamp</th>
            <th className="py-2 pr-4 text-right font-medium">Open</th>
            <th className="py-2 pr-4 text-right font-medium">High</th>
            <th className="py-2 pr-4 text-right font-medium">Low</th>
            <th className="py-2 pr-4 text-right font-medium">Close</th>
            <th className="py-2 text-right font-medium">Volume</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.ts} className="border-b border-border/50 last:border-b-0">
              <td className="tabular py-1.5 pr-4 whitespace-nowrap">
                {formatTimestamp(row.ts, timezone)}
              </td>
              <td className="tabular py-1.5 pr-4 text-right">{formatNumber(row.open)}</td>
              <td className="tabular py-1.5 pr-4 text-right">{formatNumber(row.high)}</td>
              <td className="tabular py-1.5 pr-4 text-right">{formatNumber(row.low)}</td>
              <td className="tabular py-1.5 pr-4 text-right">{formatNumber(row.close)}</td>
              <td className="tabular py-1.5 text-right">{formatInteger(row.volume)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function DatasetPreviewTable({ datasetId, totalBars, timezone }: DatasetPreviewTableProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('preview')
  const [part, setPart] = useState<PreviewPart>('head')
  const [offset, setOffset] = useState(0)
  const [jumpTo, setJumpTo] = useState('1')

  const previewQuery = useDatasetPreview(datasetId, part, PREVIEW_ROWS, viewMode === 'preview')
  const barsQuery = useDatasetBars(datasetId, offset, BROWSE_PAGE_SIZE, viewMode === 'browse')

  const activeQuery = viewMode === 'preview' ? previewQuery : barsQuery
  const rows = viewMode === 'preview' ? (previewQuery.data?.rows ?? []) : (barsQuery.data?.rows ?? [])
  const browseTotal = barsQuery.data?.total ?? totalBars
  const pageStart = browseTotal === 0 ? 0 : offset + 1
  const pageEnd = Math.min(offset + rows.length, browseTotal)

  const switchToBrowse = () => {
    setViewMode('browse')
    setOffset(0)
    setJumpTo('1')
  }

  const handleJump = () => {
    const rowNumber = Number.parseInt(jumpTo, 10)
    if (!Number.isFinite(rowNumber) || rowNumber < 1) return
    const nextOffset = Math.min(
      Math.max(0, rowNumber - 1),
      Math.max(0, browseTotal - BROWSE_PAGE_SIZE),
    )
    setOffset(nextOffset - (nextOffset % BROWSE_PAGE_SIZE))
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center justify-between gap-3">
          <span>{viewMode === 'preview' ? 'Preview' : 'All bars'}</span>
          <div className="flex flex-wrap items-center gap-1">
            <Button
              variant={viewMode === 'preview' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setViewMode('preview')}
            >
              Preview
            </Button>
            <Button
              variant={viewMode === 'browse' ? 'default' : 'outline'}
              size="sm"
              onClick={switchToBrowse}
            >
              Browse all ({formatInteger(totalBars)})
            </Button>
            {viewMode === 'preview' && (
              <>
                <Button
                  variant={part === 'head' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setPart('head')}
                >
                  First {PREVIEW_ROWS}
                </Button>
                <Button
                  variant={part === 'tail' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setPart('tail')}
                >
                  Last {PREVIEW_ROWS}
                </Button>
              </>
            )}
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {viewMode === 'browse' && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              Showing {formatInteger(pageStart)}–{formatInteger(pageEnd)} of{' '}
              {formatInteger(browseTotal)}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <Input
                className="w-28"
                type="number"
                min={1}
                max={browseTotal}
                value={jumpTo}
                onChange={(event) => setJumpTo(event.target.value)}
                aria-label="Jump to row number"
              />
              <Button type="button" variant="outline" size="sm" onClick={handleJump}>
                Jump to row
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - BROWSE_PAGE_SIZE))}
              >
                Previous
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={offset + BROWSE_PAGE_SIZE >= browseTotal}
                onClick={() => setOffset(offset + BROWSE_PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
        )}

        {activeQuery.isLoading && <p className="py-8 text-center text-sm text-muted-foreground">Loading…</p>}

        {activeQuery.isError && (
          <ErrorState
            message={getErrorMessage(activeQuery.error, 'Unable to load bars.')}
            onRetry={() => activeQuery.refetch()}
          />
        )}

        {!activeQuery.isLoading && !activeQuery.isError && rows.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            This dataset has no bars to display.
          </p>
        )}

        {!activeQuery.isLoading && !activeQuery.isError && rows.length > 0 && (
          <BarsTable rows={rows} timezone={timezone} />
        )}
      </CardContent>
    </Card>
  )
}
