import { api } from '@/lib/apiClient'

import type {
  Dataset,
  DatasetImportInput,
  DatasetListParams,
  DatasetPreview,
  PreviewPart,
} from './types'

interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
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
  form.append('timeframe', input.timeframe)
  form.append('file', input.file)
  return api.post<Dataset>('/datasets/import', form)
}

export function deleteDataset(id: string): Promise<void> {
  return api.delete<void>(`/datasets/${id}`)
}

export function revalidateDataset(id: string): Promise<Dataset> {
  return api.post<Dataset>(`/datasets/${id}/validate`)
}

export function fetchDatasetPreview(
  id: string,
  part: PreviewPart,
  rows: number,
): Promise<DatasetPreview> {
  return api.get<DatasetPreview>(`/datasets/${id}/preview`, { params: { part, rows } })
}
