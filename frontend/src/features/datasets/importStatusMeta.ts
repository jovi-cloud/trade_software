import type { ImportStatus } from './types'

interface ImportStatusMeta {
  label: string
  className: string
}

/** Mirrors features/strategies/statusMeta.ts: status colour is a domain decision. */
const IMPORT_STATUS_META: Record<ImportStatus, ImportStatusMeta> = {
  processing: {
    label: 'Processing',
    className: 'border-transparent bg-primary text-primary-foreground',
  },
  completed: { label: 'Ready', className: 'border-transparent bg-profit/15 text-profit' },
  failed: { label: 'Failed', className: 'border-transparent bg-loss/15 text-loss' },
}

export function importStatusMeta(status: ImportStatus): ImportStatusMeta {
  return IMPORT_STATUS_META[status]
}
