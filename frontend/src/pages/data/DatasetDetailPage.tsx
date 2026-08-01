import { Archive, ArrowLeft, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { Breadcrumbs } from '@/components/common/Breadcrumbs'
import { ErrorState } from '@/components/common/ErrorState'
import { PageHeader } from '@/components/common/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ArchiveDatasetDialog } from '@/features/datasets/components/ArchiveDatasetDialog'
import { DatasetPreviewTable } from '@/features/datasets/components/DatasetPreviewTable'
import { DatasetStatisticsCard } from '@/features/datasets/components/DatasetStatisticsCard'
import { DatasetTimezoneBanner } from '@/features/datasets/components/DatasetTimezoneBanner'
import { DatasetVersionsPanel } from '@/features/datasets/components/DatasetVersionsPanel'
import { DeleteDatasetDialog } from '@/features/datasets/components/DeleteDatasetDialog'
import { QualityScoreBreakdownPanel } from '@/features/datasets/components/QualityScoreBreakdown'
import { ValidationReportCard } from '@/features/datasets/components/ValidationReportCard'
import { importStatusMeta } from '@/features/datasets/importStatusMeta'
import {
  useArchiveDataset,
  useDataset,
  useDatasetImports,
  useDatasetVersions,
  useDeleteDataset,
} from '@/features/datasets/queries'
import { getErrorMessage } from '@/lib/apiClient'
import { formatDate, formatInteger } from '@/lib/format'

export default function DatasetDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const datasetQuery = useDataset(id)
  const versionsQuery = useDatasetVersions(id)
  const importsQuery = useDatasetImports(id)
  const archiveDataset = useArchiveDataset()
  const deleteDataset = useDeleteDataset()
  const [showArchive, setShowArchive] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const [showQualityBreakdown, setShowQualityBreakdown] = useState(false)

  const isLoading = datasetQuery.isLoading || versionsQuery.isLoading || importsQuery.isLoading
  const isError = datasetQuery.isError
  const dataset = datasetQuery.data

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  if (isError || !dataset) {
    return (
      <ErrorState
        message={getErrorMessage(datasetQuery.error, 'Dataset not found or could not be loaded.')}
        onRetry={() => datasetQuery.refetch()}
      />
    )
  }

  const statusMeta = importStatusMeta(dataset.import_status)
  const pipeline = dataset.pipeline_report
  const qualityScore = dataset.quality_score ?? pipeline?.quality_score ?? null

  return (
    <div>
      <Breadcrumbs
        items={[
          { label: 'Data', to: '/data' },
          { label: dataset.name },
        ]}
      />

      <PageHeader
        title={dataset.name}
        description={`${dataset.symbol} · ${dataset.exchange} · ${dataset.timeframe}`}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" asChild>
              <Link to="/data">
                <ArrowLeft /> Back
              </Link>
            </Button>
            {dataset.lifecycle !== 'archived' && (
              <Button variant="outline" onClick={() => setShowArchive(true)}>
                <Archive /> Archive
              </Button>
            )}
            <Button variant="destructive" onClick={() => setShowDelete(true)}>
              <Trash2 /> Delete
            </Button>
          </div>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-2">
        <Badge className={statusMeta.className}>{statusMeta.label}</Badge>
        {dataset.lifecycle === 'archived' && <Badge variant="secondary">Archived</Badge>}
        <span className="text-sm text-muted-foreground">
          {formatInteger(dataset.row_count)} bars
        </span>
        {dataset.start_date && dataset.end_date && (
          <span className="text-sm text-muted-foreground">
            {formatDate(dataset.start_date)} → {formatDate(dataset.end_date)}
          </span>
        )}
        <span className="text-sm text-muted-foreground">Timezone: {dataset.timezone}</span>
      </div>

      <DatasetTimezoneBanner dataset={dataset} onFixed={() => datasetQuery.refetch()} />

      <DatasetStatisticsCard
        dataset={dataset}
        showQualityBreakdown={showQualityBreakdown}
        onToggleQualityBreakdown={() => setShowQualityBreakdown((open) => !open)}
      />
      {showQualityBreakdown && (
        <QualityScoreBreakdownPanel
          datasetId={dataset.id}
          pipeline={pipeline}
          qualityScore={qualityScore}
          sessionOpen={dataset.session_open}
          sessionClose={dataset.session_close}
          onCleanComplete={() => datasetQuery.refetch()}
        />
      )}
      <ValidationReportCard
        dataset={dataset}
        onShowQualityBreakdown={() => {
          setShowQualityBreakdown(true)
          requestAnimationFrame(() => {
            document.getElementById('quality-breakdown')?.scrollIntoView({ behavior: 'smooth' })
          })
        }}
      />

      <div className="mb-6 space-y-4">
        <DatasetVersionsPanel
          datasetId={dataset.id}
          currentVersionNumber={dataset.current_version_number}
          versions={versionsQuery.data ?? []}
          imports={importsQuery.data ?? []}
        />
        <DatasetPreviewTable
          key={`${dataset.id}-${dataset.current_version_number ?? 0}-${dataset.row_count}`}
          datasetId={dataset.id}
          totalBars={dataset.row_count}
          timezone={dataset.timezone}
        />
      </div>

      <ArchiveDatasetDialog
        dataset={showArchive ? dataset : null}
        onOpenChange={(open) => !open && setShowArchive(false)}
        onConfirm={() => {
          archiveDataset.mutate(dataset.id, {
            onSuccess: () => setShowArchive(false),
          })
        }}
        isArchiving={archiveDataset.isPending}
      />

      <DeleteDatasetDialog
        dataset={showDelete ? dataset : null}
        onOpenChange={(open) => {
          if (!open) {
            setShowDelete(false)
            deleteDataset.reset()
          }
        }}
        onConfirm={() => {
          deleteDataset.mutate(dataset.id, {
            onSuccess: () => {
              setShowDelete(false)
              navigate('/data')
            },
          })
        }}
        isDeleting={deleteDataset.isPending}
        errorMessage={
          deleteDataset.isError
            ? getErrorMessage(deleteDataset.error, 'Unable to delete this dataset.')
            : null
        }
      />
    </div>
  )
}
