import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { qk } from '@/lib/queryKeys'

import {
  archiveDataset,
  cleanDataset,
  deleteDataset,
  fetchDataset,
  fetchDatasetImports,
  fetchDatasetBars,
  fetchDatasetPreview,
  fetchDatasetReferences,
  fetchDatasets,
  fetchDatasetVersions,
  importDataset,
  revalidateDataset,
} from './api'
import type {
  Dataset,
  DatasetCleanInput,
  DatasetImportInput,
  DatasetListParams,
  PreviewPart,
} from './types'

function invalidateDatasetBarCaches(queryClient: ReturnType<typeof useQueryClient>, datasetId: string) {
  queryClient.invalidateQueries({ queryKey: [...qk.datasets.all, 'preview', datasetId] })
  queryClient.invalidateQueries({ queryKey: [...qk.datasets.all, 'bars', datasetId] })
}

function refreshDatasetCaches(
  queryClient: ReturnType<typeof useQueryClient>,
  dataset: Dataset,
) {
  queryClient.setQueryData(qk.datasets.detail(dataset.id), dataset)
  queryClient.invalidateQueries({ queryKey: qk.datasets.all })
  queryClient.invalidateQueries({ queryKey: qk.datasets.versions(dataset.id) })
  queryClient.invalidateQueries({ queryKey: qk.datasets.imports(dataset.id) })
  invalidateDatasetBarCaches(queryClient, dataset.id)
}

export function useDatasets(params: DatasetListParams) {
  return useQuery({
    queryKey: qk.datasets.list(params),
    queryFn: () => fetchDatasets(params),
  })
}

export function useDatasetVersions(id: string) {
  return useQuery({
    queryKey: qk.datasets.versions(id),
    queryFn: () => fetchDatasetVersions(id),
    enabled: id.length > 0,
  })
}

export function useDatasetImports(id: string) {
  return useQuery({
    queryKey: qk.datasets.imports(id),
    queryFn: () => fetchDatasetImports(id),
    enabled: id.length > 0,
  })
}

export function useDataset(id: string) {
  return useQuery({
    queryKey: qk.datasets.detail(id),
    queryFn: () => fetchDataset(id),
    enabled: id.length > 0,
  })
}

export function useDatasetPreview(
  id: string,
  part: PreviewPart,
  rows: number,
  enabled = true,
) {
  return useQuery({
    queryKey: qk.datasets.preview(id, part, rows),
    queryFn: () => fetchDatasetPreview(id, part, rows),
    enabled: enabled && id.length > 0,
  })
}

export function useDatasetBars(id: string, offset: number, limit: number, enabled = true) {
  return useQuery({
    queryKey: qk.datasets.bars(id, offset, limit),
    queryFn: () => fetchDatasetBars(id, offset, limit),
    enabled: enabled && id.length > 0,
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

export function useArchiveDataset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => archiveDataset(id),
    onSuccess: (dataset) => {
      queryClient.setQueryData(qk.datasets.detail(dataset.id), dataset)
      queryClient.invalidateQueries({ queryKey: qk.datasets.all })
    },
  })
}

export function useDatasetReferences(id: string, enabled: boolean) {
  return useQuery({
    queryKey: [...qk.datasets.detail(id), 'references'],
    queryFn: () => fetchDatasetReferences(id),
    enabled: enabled && id.length > 0,
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

export function useCleanDataset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, input }: { id: string; input: DatasetCleanInput }) =>
      cleanDataset(id, input),
    onSuccess: (dataset) => {
      refreshDatasetCaches(queryClient, dataset)
    },
  })
}

export function useRevalidateDataset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, timezone }: { id: string; timezone?: string }) =>
      revalidateDataset(id, timezone ? { timezone } : undefined),
    onSuccess: (dataset) => {
      refreshDatasetCaches(queryClient, dataset)
    },
  })
}
