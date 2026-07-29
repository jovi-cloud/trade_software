import type { DatasetListParams, PreviewPart } from '@/features/datasets/types'
import type { StrategyListParams } from '@/features/strategies/types'

/**
 * Centralised TanStack Query cache keys.
 *
 * Every key lives here so that invalidation after a mutation is a lookup
 * rather than a guess. Namespaces are added as features land.
 */
export const qk = {
  system: {
    all: ['system'] as const,
    health: () => [...qk.system.all, 'health'] as const,
  },
  strategies: {
    all: ['strategies'] as const,
    list: (params: StrategyListParams) => [...qk.strategies.all, 'list', params] as const,
    detail: (id: string) => [...qk.strategies.all, 'detail', id] as const,
    stats: () => [...qk.strategies.all, 'stats'] as const,
    code: (id: string) => [...qk.strategies.all, 'code', id] as const,
  },
  datasets: {
    all: ['datasets'] as const,
    list: (params: DatasetListParams) => [...qk.datasets.all, 'list', params] as const,
    detail: (id: string) => [...qk.datasets.all, 'detail', id] as const,
    preview: (id: string, part: PreviewPart, rows: number) =>
      [...qk.datasets.all, 'preview', id, part, rows] as const,
  },
  // Phase 1: instruments
  // Phase 2: strategy versions
  // Phase 3: backtests, jobs
  // Phase 4: results
} as const
