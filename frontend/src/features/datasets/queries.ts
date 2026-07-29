import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { qk } from '@/lib/queryKeys'

import {
  deleteDataset,
  fetchDataset,
  fetchDatasetPreview,
  fetchDatasets,
  importDataset,
  revalidateDataset,
} from './api'
import type { DatasetImportInput, DatasetListParams, PreviewPart } from './types'

export function useDatasets(params: DatasetListParams) {
  return useQuery({
    queryKey: qk.datasets.list(params),
    queryFn: () => fetchDatasets(params),
  })
}

export function useDataset(id: string) {
  return useQuery({
    queryKey: qk.datasets.detail(id),
    queryFn: () => fetchDataset(id),
    enabled: id.length > 0,
  })
}

export function useDatasetPreview(id: string, part: PreviewPart, rows: number) {
  return useQuery({
    queryKey: qk.datasets.preview(id, part, rows),
    queryFn: () => fetchDatasetPreview(id, part, rows),
    enabled: id.length > 0,
  })
}

export function useImportDataset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: DatasetImportInput) => importDataset(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.datasets.all })
    },
  })
}

export function useDeleteDataset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteDataset(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.datasets.all })
    },
  })
}

export function useRevalidateDataset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => revalidateDataset(id),
    onSuccess: (dataset) => {
      queryClient.setQueryData(qk.datasets.detail(dataset.id), dataset)
      queryClient.invalidateQueries({ queryKey: qk.datasets.all })
    },
  })
}
