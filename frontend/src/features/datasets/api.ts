import { api } from '@/lib/apiClient'

import type {
  DataImport,
  Dataset,
  DatasetBarsPage,
  DatasetCleanInput,
  DatasetImportInput,
  DatasetListParams,
  DatasetPreview,
  DatasetVersion,
  PreviewPart,
  Timeframe,
} from './types'

interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export function fetchDatasetVersions(datasetId: string): Promise<DatasetVersion[]> {
  return api.get<DatasetVersion[]>(`/datasets/${datasetId}/versions`)
}

export function fetchDatasetImports(datasetId: string): Promise<DataImport[]> {
  return api.get<DataImport[]>(`/datasets/${datasetId}/imports`)
}

export function fetchDatasets(params: DatasetListParams): Promise<Page<Dataset>> {
  return api.get<Page<Dataset>>('/datasets', { params })
}

export function fetchDataset(id: string): Promise<Dataset> {
  return api.get<Dataset>(`/datasets/${id}`)
}

export function importDataset(input: DatasetImportInput): Promise<Dataset> {
  const form = new FormData()
  form.append('name', input.name)
  form.append('symbol', input.symbol)
  form.append('exchange', input.exchange)
  if (input.timeframe) form.append('timeframe', input.timeframe)
  if (input.timezone) form.append('timezone', input.timezone)
  if (input.sessionOpen) form.append('session_open', input.sessionOpen)
  if (input.sessionClose) form.append('session_close', input.sessionClose)
  form.append('file', input.file)
  return api.post<Dataset>('/datasets/import', form)
}

export interface DatasetReferences {
  reference_count: number
  backtest_runs: Array<{
    run_id: string
    strategy_name: string
    dataset_version_number?: number | null
    execution_completed_at: string
  }>
}

export function archiveDataset(id: string): Promise<Dataset> {
  return api.post<Dataset>(`/datasets/${id}/archive`)
}

export function fetchDatasetReferences(id: string): Promise<DatasetReferences> {
  return api.get<DatasetReferences>(`/datasets/${id}/references`)
}

export function deleteDataset(id: string): Promise<void> {
  return api.delete<void>(`/datasets/${id}`)
}

export function cleanDataset(id: string, input: DatasetCleanInput): Promise<Dataset> {
  return api.post<Dataset>(`/datasets/${id}/clean`, {
    remove_outside_session: input.remove_outside_session,
    remove_weekend_bars: input.remove_weekend_bars,
    remove_holiday_bars: input.remove_holiday_bars,
    remove_intraday_spike_days_over_10pct: input.remove_intraday_spike_days_over_10pct,
    remove_intraday_spike_days_over_20pct: input.remove_intraday_spike_days_over_20pct,
    remove_cross_day_spike_days_over_10pct: input.remove_cross_day_spike_days_over_10pct,
    remove_cross_day_spike_days_over_20pct: input.remove_cross_day_spike_days_over_20pct,
  })
}

export function revalidateDataset(
  id: string,
  options?: { timezone?: string },
): Promise<Dataset> {
  return api.post<Dataset>(`/datasets/${id}/validate`, options ?? {})
}

export function fetchDatasetPreview(
  id: string,
  part: PreviewPart,
  rows: number,
): Promise<DatasetPreview> {
  return api.get<DatasetPreview>(`/datasets/${id}/preview`, { params: { part, rows } })
}

export function fetchDatasetBars(
  id: string,
  offset: number,
  limit: number,
): Promise<DatasetBarsPage> {
  return api.get<DatasetBarsPage>(`/datasets/${id}/bars`, { params: { offset, limit } })
}

export interface ImportPreview {
  columns: string[]
  suggested_mapping: Record<string, string>
  sample_rows: Record<string, unknown>[]
  row_count_estimate: number
}

export function previewImportFile(file: File): Promise<ImportPreview> {
  const form = new FormData()
  form.append('file', file)
  return api.post<ImportPreview>('/datasets/import/preview', form)
}

export type { Timeframe }
