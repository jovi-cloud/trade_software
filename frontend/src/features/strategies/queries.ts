import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { qk } from '@/lib/queryKeys'

import {
  createStrategy,
  deleteStrategy,
  fetchStrategies,
  fetchStrategy,
  fetchStrategyCode,
  fetchStrategyStats,
  saveStrategyCode,
  updateStrategy,
  validateStrategyCode,
} from './api'
import type {
  StrategyCodeUpdateInput,
  StrategyCodeValidateInput,
  StrategyCreateInput,
  StrategyListParams,
  StrategyUpdateInput,
} from './types'

export function useStrategies(params: StrategyListParams) {
  return useQuery({
    queryKey: qk.strategies.list(params),
    queryFn: () => fetchStrategies(params),
  })
}

export function useStrategy(id: string) {
  return useQuery({
    queryKey: qk.strategies.detail(id),
    queryFn: () => fetchStrategy(id),
    enabled: id.length > 0,
  })
}

export function useStrategyStats() {
  return useQuery({
    queryKey: qk.strategies.stats(),
    queryFn: fetchStrategyStats,
    staleTime: 10_000,
  })
}

export function useCreateStrategy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: StrategyCreateInput) => createStrategy(input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.strategies.all })
    },
  })
}

export function useUpdateStrategy(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: StrategyUpdateInput) => updateStrategy(id, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.strategies.all })
    },
  })
}

export function useDeleteStrategy() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => deleteStrategy(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: qk.strategies.all })
    },
  })
}

export function useStrategyCode(strategyId: string) {
  return useQuery({
    queryKey: qk.strategies.code(strategyId),
    queryFn: () => fetchStrategyCode(strategyId),
    enabled: strategyId.length > 0,
  })
}

export function useSaveStrategyCode(strategyId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: StrategyCodeUpdateInput) => saveStrategyCode(strategyId, input),
    onSuccess: (code) => {
      queryClient.setQueryData(qk.strategies.code(strategyId), code)
    },
  })
}

export function useValidateStrategyCode(strategyId: string) {
  return useMutation({
    mutationFn: (input: StrategyCodeValidateInput) => validateStrategyCode(strategyId, input),
  })
}
