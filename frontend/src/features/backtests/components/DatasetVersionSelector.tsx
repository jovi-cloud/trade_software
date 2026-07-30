import { AlertTriangle } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { formatDate, formatInteger } from '@/lib/format'

import type { DatasetVersion } from '@/features/datasets/types'

const LATEST = 'latest'

interface DatasetVersionSelectorProps {
  datasetId: string
  currentVersionNumber?: number | null
  versions: DatasetVersion[]
  selectedVersionNumber: number | null
  onChange: (versionNumber: number | null) => void
}

export function DatasetVersionSelector({
  datasetId,
  currentVersionNumber,
  versions,
  selectedVersionNumber,
  onChange,
}: DatasetVersionSelectorProps) {
  const validVersions = versions.filter((version) => version.status === 'valid')
  const selected =
    selectedVersionNumber === null
      ? validVersions.find((version) => version.version_number === currentVersionNumber) ??
        validVersions[0]
      : validVersions.find((version) => version.version_number === selectedVersionNumber)

  const isHistorical =
    selectedVersionNumber !== null &&
    currentVersionNumber !== null &&
    currentVersionNumber !== undefined &&
    selectedVersionNumber !== currentVersionNumber

  if (!datasetId || validVersions.length === 0) {
    return null
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2">
        <Label htmlFor="dataset-version">Dataset version</Label>
        <Select
          value={selectedVersionNumber === null ? LATEST : String(selectedVersionNumber)}
          onValueChange={(value) =>
            onChange(value === LATEST ? null : Number.parseInt(value, 10))
          }
        >
          <SelectTrigger id="dataset-version">
            <SelectValue placeholder="Select a version" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={LATEST}>
              Latest (v{currentVersionNumber ?? validVersions[0]?.version_number})
            </SelectItem>
            {validVersions.map((version) => (
              <SelectItem key={version.id} value={String(version.version_number)}>
                Version {version.version_number}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {isHistorical && (
        <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-900 dark:text-amber-100">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <p>
            You are running against Dataset Version {selectedVersionNumber}. Newer versions exist
            (current: v{currentVersionNumber}).
          </p>
        </div>
      )}

      {selected && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              Version {selected.version_number}
              {selected.version_number === currentVersionNumber && (
                <Badge variant="secondary">Current</Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <p className="text-xs text-muted-foreground">Imported</p>
              <p>{formatDate(selected.created_at)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Quality score</p>
              <p className="tabular">{selected.quality_score ?? '--'}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Rows</p>
              <p className="tabular">{formatInteger(selected.row_count)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Date range</p>
              <p>
                {formatDate(selected.start_date)} – {formatDate(selected.end_date)}
              </p>
            </div>
            <div className="sm:col-span-2">
              <p className="text-xs text-muted-foreground">Fingerprint</p>
              <p className="truncate font-mono text-xs">{selected.fingerprint}</p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
