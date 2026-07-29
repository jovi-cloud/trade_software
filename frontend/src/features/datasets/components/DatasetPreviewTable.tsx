import { useState } from 'react'

import { ErrorState } from '@/components/common/ErrorState'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { getErrorMessage } from '@/lib/apiClient'
import { formatInteger, formatNumber, formatTimestamp } from '@/lib/format'

import { useDatasetPreview } from '../queries'
import type { PreviewPart } from '../types'

const PREVIEW_ROWS = 20

interface DatasetPreviewTableProps {
  datasetId: string
}

export function DatasetPreviewTable({ datasetId }: DatasetPreviewTableProps) {
  const [part, setPart] = useState<PreviewPart>('head')
  const { data, isLoading, isError, error, refetch } = useDatasetPreview(
    datasetId,
    part,
    PREVIEW_ROWS,
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          <span>Preview</span>
          <div className="flex items-center gap-1">
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
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <Skeleton className="h-64" />}

        {isError && (
          <ErrorState
            message={getErrorMessage(error, 'Unable to load the preview.')}
            onRetry={() => refetch()}
          />
        )}

        {!isLoading && !isError && data && data.rows.length === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            This dataset has no bars to preview.
          </p>
        )}

        {!isLoading && !isError && data && data.rows.length > 0 && (
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
                {data.rows.map((row) => (
                  <tr key={row.ts} className="border-b border-border/50 last:border-b-0">
                    <td className="tabular py-1.5 pr-4 whitespace-nowrap">
                      {formatTimestamp(row.ts)}
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
        )}
      </CardContent>
    </Card>
  )
}
