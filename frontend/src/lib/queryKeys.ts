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
  backtests: {
    all: ['backtests'] as const,
    execute: () => [...qk.backtests.all, 'execute'] as const,
  },
  backtestRuns: {
    all: ['backtest-runs'] as const,
    list: (params: Record<string, unknown>) => [...qk.backtestRuns.all, 'list', params] as const,
    detail: (id: string) => [...qk.backtestRuns.all, 'detail', id] as const,
  },
  explain: {
    all: ['explain'] as const,
    events: (runId: string, filters: Record<string, unknown>) =>
      [...qk.explain.all, 'events', runId, filters] as const,
    trade: (runId: string, tradeId: number) =>
      [...qk.explain.all, 'trade', runId, tradeId] as const,
    tradeEvents: (runId: string, tradeId: number) =>
      [...qk.explain.all, 'trade-events', runId, tradeId] as const,
    bar: (runId: string, barIndex: number) => [...qk.explain.all, 'bar', runId, barIndex] as const,
  },
  strategyLibrary: {
    all: ['strategy-library'] as const,
    list: (params: Record<string, unknown>) => [...qk.strategyLibrary.all, 'list', params] as const,
    facets: () => [...qk.strategyLibrary.all, 'facets'] as const,
    detail: (id: string) => [...qk.strategyLibrary.all, 'detail', id] as const,
    documentation: (id: string) => [...qk.strategyLibrary.all, 'documentation', id] as const,
  },
} as const
