import type { DatasetLifecycle, DatasetStatus, ImportStatus } from './types'

interface StatusMeta {
  label: string
  className: string
}

/** Mirrors features/strategies/statusMeta.ts: status colour is a domain decision. */
const IMPORT_STATUS_META: Record<ImportStatus, StatusMeta> = {
  processing: {
    label: 'Processing',
    className: 'border-transparent bg-primary text-primary-foreground',
  },
  completed: { label: 'Ready', className: 'border-transparent bg-profit/15 text-profit' },
  failed: { label: 'Failed', className: 'border-transparent bg-loss/15 text-loss' },
}

const DATASET_STATUS_META: Record<DatasetStatus, StatusMeta> = {
  uploaded: {
    label: 'Uploaded',
    className: 'border-transparent bg-muted text-muted-foreground',
  },
  validating: {
    label: 'Validating',
    className: 'border-transparent bg-primary text-primary-foreground',
  },
  valid: { label: 'Valid', className: 'border-transparent bg-profit/15 text-profit' },
  invalid: { label: 'Invalid', className: 'border-transparent bg-loss/15 text-loss' },
  failed: { label: 'Failed', className: 'border-transparent bg-loss/15 text-loss' },
}

const LIFECYCLE_META: Record<DatasetLifecycle, StatusMeta> = {
  active: { label: 'Active', className: 'border-transparent bg-profit/15 text-profit' },
  archived: {
    label: 'Archived',
    className: 'border-transparent bg-muted text-muted-foreground',
  },
  deleted: { label: 'Deleted', className: 'border-transparent bg-loss/15 text-loss' },
}

export function importStatusMeta(status: ImportStatus): StatusMeta {
  return IMPORT_STATUS_META[status]
}

export function datasetStatusMeta(status: DatasetStatus): StatusMeta {
  return DATASET_STATUS_META[status]
}

export function datasetLifecycleMeta(lifecycle: DatasetLifecycle): StatusMeta {
  return LIFECYCLE_META[lifecycle]
}

export function datasetDisplayStatus(dataset: {
  status?: DatasetStatus
  lifecycle?: DatasetLifecycle
  import_status: ImportStatus
}): StatusMeta {
  if (dataset.lifecycle && dataset.lifecycle !== 'active') {
    return datasetLifecycleMeta(dataset.lifecycle)
  }
  if (dataset.status) {
    return datasetStatusMeta(dataset.status)
  }
  return importStatusMeta(dataset.import_status)
}
