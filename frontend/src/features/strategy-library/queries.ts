import { useMutation, useQuery } from '@tanstack/react-query'

import { qk } from '@/lib/queryKeys'

import {
  fetchLibraryFacets,
  fetchLibraryStrategies,
  fetchLibraryStrategy,
  fetchLibraryStrategyDocumentation,
  validateLibraryStrategyParams,
} from './api'
import type { LibraryListParams, ValidateParamsInput } from './types'

export function useLibraryStrategies(params: LibraryListParams) {
  return useQuery({
    queryKey: qk.strategyLibrary.list(params),
    queryFn: () => fetchLibraryStrategies(params),
  })
}

export function useLibraryFacets() {
  return useQuery({
    queryKey: qk.strategyLibrary.facets(),
    queryFn: fetchLibraryFacets,
    staleTime: 60_000,
  })
}

export function useLibraryStrategy(strategyId: string) {
  return useQuery({
    queryKey: qk.strategyLibrary.detail(strategyId),
    queryFn: () => fetchLibraryStrategy(strategyId),
    enabled: strategyId.length > 0,
  })
}

export function useLibraryStrategyDocumentation(strategyId: string) {
  return useQuery({
    queryKey: qk.strategyLibrary.documentation(strategyId),
    queryFn: () => fetchLibraryStrategyDocumentation(strategyId),
    enabled: strategyId.length > 0,
  })
}

export function useValidateLibraryParams(strategyId: string) {
  return useMutation({
    mutationFn: (input: ValidateParamsInput) => validateLibraryStrategyParams(strategyId, input),
  })
}
