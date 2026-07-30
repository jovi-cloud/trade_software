import { api } from '@/lib/apiClient'
import type { components } from '@/types/api'

import type {
  LibraryFacets,
  LibraryListParams,
  LibraryStrategy,
  LibraryStrategyListItem,
  ParamValidation,
  StrategyDocumentation,
  ValidateParamsInput,
} from './types'

type Page<T> = components['schemas']['Page_LibraryStrategyListItem_'] & { items: T[] }
type ParameterSet = components['schemas']['ParameterSetRead']

export function fetchLibraryStrategies(
  params: LibraryListParams,
): Promise<Page<LibraryStrategyListItem>> {
  return api.get<Page<LibraryStrategyListItem>>('/strategy-library', { params })
}

export function fetchLibraryFacets(): Promise<LibraryFacets> {
  return api.get<LibraryFacets>('/strategy-library/facets')
}

export function fetchLibraryStrategy(strategyId: string): Promise<LibraryStrategy> {
  return api.get<LibraryStrategy>(`/strategy-library/${strategyId}`)
}

export function fetchLibraryStrategyParameters(strategyId: string): Promise<ParameterSet> {
  return api.get<ParameterSet>(`/strategy-library/${strategyId}/parameters`)
}

export function fetchLibraryStrategyDocumentation(
  strategyId: string,
): Promise<StrategyDocumentation> {
  return api.get<StrategyDocumentation>(`/strategy-library/${strategyId}/documentation`)
}

export function validateLibraryStrategyParams(
  strategyId: string,
  input: ValidateParamsInput,
): Promise<ParamValidation> {
  return api.post<ParamValidation>(`/strategy-library/${strategyId}/validate`, input)
}
