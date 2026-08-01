import type { components } from '@/types/api'

export type DatasetLifecycle = 'active' | 'archived' | 'deleted'

export type Dataset = components['schemas']['DatasetRead'] & {
  status?: DatasetStatus
  lifecycle?: DatasetLifecycle
  current_version_id?: string | null
  current_version_number?: number | null
  version_count?: number
  session_open?: string
  session_close?: string
}
export type DatasetVersion = {
  id: string
  dataset_id: string
  version_number: number
  data_import_id?: string | null
  file_path: string
  file_size_bytes: number
  parquet_hash: string
  fingerprint: string
  row_count: number
  start_date: string | null
  end_date: string | null
  timezone: string
  detected_timeframe?: Timeframe | null
  quality_score?: number | null
  status: string
  error_message?: string | null
  created_at: string
}

export type DataImport = {
  id: string
  dataset_id: string
  dataset_version_id?: string | null
  filename: string
  file_hash: string
  rows_read: number
  rows_written: number
  rows_rejected: number
  duplicates_removed: number
  gaps_detected: number
  quality_score?: number | null
  status: ImportStatus
  error_message?: string | null
  created_at: string
}
export type DatasetValidationReport = components['schemas']['DatasetValidationReport']
export type DatasetPreview = components['schemas']['DatasetPreview']
export type BarRow = components['schemas']['BarRow']
export interface DatasetBarsPage {
  rows: BarRow[]
  total: number
  limit: number
  offset: number
}
export type ImportStatus = components['schemas']['ImportStatus']
export type DatasetStatus =
  | 'uploaded'
  | 'validating'
  | 'valid'
  | 'invalid'
  | 'failed'
export type Timeframe = components['schemas']['Timeframe'] | '10m'

export type DatasetSort = 'updated_at' | 'name' | 'row_count'
export type SortOrder = 'asc' | 'desc'
export type PreviewPart = 'head' | 'tail'

export interface DatasetListParams {
  q?: string
  timeframe?: Timeframe
  sort?: DatasetSort
  order?: SortOrder
  limit?: number
  offset?: number
  [key: string]: string | number | boolean | undefined | null
}

export interface DatasetCleanInput {
  remove_outside_session: boolean
  remove_weekend_bars: boolean
  remove_holiday_bars: boolean
  remove_intraday_spike_days_over_10pct: boolean
  remove_intraday_spike_days_over_20pct: boolean
  remove_cross_day_spike_days_over_10pct: boolean
  remove_cross_day_spike_days_over_20pct: boolean
}

export interface DatasetImportInput {
  name: string
  symbol: string
  exchange: string
  timeframe?: Timeframe
  timezone?: string
  sessionOpen?: string
  sessionClose?: string
  file: File
}

export const ACCEPTED_FILE_TYPES = '.csv,.xlsx,.xls,.parquet,.pq'

export const TIMEFRAMES: Timeframe[] = [
  '1m',
  '3m',
  '5m',
  '10m',
  '15m',
  '30m',
  '1h',
  '2h',
  '4h',
  '1d',
  '1w',
]

/** Canonical source columns after header normalisation. */
export const REQUIRED_CSV_COLUMNS = ['timestamp', 'open', 'high', 'low', 'close', 'volume'] as const
