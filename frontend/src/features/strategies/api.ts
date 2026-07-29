import { api } from '@/lib/apiClient'

import type {
  Page,
  Strategy,
  StrategyCode,
  StrategyCodeUpdateInput,
  StrategyCodeValidateInput,
  StrategyCreateInput,
  StrategyListParams,
  StrategyStats,
  StrategyUpdateInput,
  StrategyValidationResult,
} from './types'

export function fetchStrategies(params: StrategyListParams): Promise<Page<Strategy>> {
  return api.get<Page<Strategy>>('/strategies', { params })
}

export function fetchStrategy(id: string): Promise<Strategy> {
  return api.get<Strategy>(`/strategies/${id}`)
}

export function fetchStrategyStats(): Promise<StrategyStats> {
  return api.get<StrategyStats>('/strategies/stats')
}

export function createStrategy(input: StrategyCreateInput): Promise<Strategy> {
  return api.post<Strategy>('/strategies', input)
}

export function updateStrategy(id: string, input: StrategyUpdateInput): Promise<Strategy> {
  return api.patch<Strategy>(`/strategies/${id}`, input)
}

export function deleteStrategy(id: string): Promise<void> {
  return api.delete<void>(`/strategies/${id}`)
}

export function fetchStrategyCode(strategyId: string): Promise<StrategyCode> {
  return api.get<StrategyCode>(`/strategies/${strategyId}/code`)
}

export function saveStrategyCode(
  strategyId: string,
  input: StrategyCodeUpdateInput,
): Promise<StrategyCode> {
  return api.put<StrategyCode>(`/strategies/${strategyId}/code`, input)
}

export function validateStrategyCode(
  strategyId: string,
  input: StrategyCodeValidateInput,
): Promise<StrategyValidationResult> {
  return api.post<StrategyValidationResult>(`/strategies/${strategyId}/validate`, input)
}
