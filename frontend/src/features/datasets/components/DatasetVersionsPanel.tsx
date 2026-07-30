import { Download, History } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate, formatInteger } from '@/lib/format'

import { importStatusMeta } from '../importStatusMeta'
import type { DataImport, DatasetVersion } from '../types'

interface DatasetVersionsPanelProps {
  datasetId: string
  currentVersionNumber?: number | null
  versions: DatasetVersion[]
  imports: DataImport[]
}

function versionStatusLabel(status: string): string {
  switch (status) {
    case 'valid':
      return 'Valid'
    case 'validating':
      return 'Validating'
    case 'invalid':
      return 'Invalid'
    case 'failed':
      return 'Failed'
    default:
      return status
  }
}

export function DatasetVersionsPanel({
  datasetId,
  currentVersionNumber,
  versions,
  imports,
}: DatasetVersionsPanelProps) {
  const importByVersion = new Map(
    imports
      .filter((item) => item.dataset_version_id)
      .map((item) => [item.dataset_version_id as string, item]),
  )

  return (
    <div className="mb-4 space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <History className="size-4" />
            Versions
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {versions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No versions imported yet.</p>
          ) : (
            versions.map((version) => {
              const isCurrent = version.version_number === currentVersionNumber
              const importRecord = version.data_import_id
                ? importByVersion.get(version.data_import_id)
                : undefined
              return (
                <div
                  key={version.id}
                  className="rounded-lg border p-3 text-sm"
                  data-current={isCurrent}
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="font-medium">v{version.version_number}</span>
                    {isCurrent && <Badge variant="secondary">Current</Badge>}
                    <Badge variant="outline">{versionStatusLabel(version.status)}</Badge>
                    {version.quality_score !== null && version.quality_score !== undefined && (
                      <Badge variant="outline">Quality {version.quality_score}</Badge>
                    )}
                  </div>
                  <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                    <div>
                      <dt className="text-xs text-muted-foreground">Rows</dt>
                      <dd className="tabular">{formatInteger(version.row_count)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted-foreground">Imported</dt>
                      <dd>{formatDate(version.created_at)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted-foreground">Fingerprint</dt>
                      <dd className="truncate font-mono text-xs">{version.fingerprint}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-muted-foreground">File size</dt>
                      <dd className="tabular">{formatInteger(version.file_size_bytes)} bytes</dd>
                    </div>
                  </dl>
                  {importRecord && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      Source: {importRecord.filename} · {importRecord.rows_written} rows written ·{' '}
                      {importRecord.duplicates_removed} duplicates removed
                    </p>
                  )}
                  {version.status === 'valid' && (
                    <div className="mt-3">
                      <Button variant="outline" size="sm" asChild>
                        <a
                          href={`/api/v1/datasets/${datasetId}/versions/${version.version_number}/download`}
                          download
                        >
                          <Download className="size-3.5" />
                          Download parquet
                        </a>
                      </Button>
                    </div>
                  )}
                </div>
              )
            })
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Import history</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {imports.length === 0 ? (
            <p className="text-sm text-muted-foreground">No imports recorded.</p>
          ) : (
            imports.map((record) => {
              const meta = importStatusMeta(record.status)
              return (
                <div key={record.id} className="rounded-lg border p-3 text-sm">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="font-medium">{record.filename}</span>
                    <Badge className={meta.className}>{meta.label}</Badge>
                    {record.quality_score !== null && record.quality_score !== undefined && (
                      <Badge variant="outline">Quality {record.quality_score}</Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(record.created_at)} · read {record.rows_read} · written{' '}
                    {record.rows_written} · rejected {record.rows_rejected}
                  </p>
                  {record.error_message && (
                    <p className="mt-1 text-xs text-destructive">{record.error_message}</p>
                  )}
                </div>
              )
            })
          )}
        </CardContent>
      </Card>
    </div>
  )
}
