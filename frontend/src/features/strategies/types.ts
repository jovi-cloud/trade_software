import type { components } from '@/types/api'

export type Strategy = components['schemas']['StrategyRead']
export type StrategyCreateInput = components['schemas']['StrategyCreate']
export type StrategyUpdateInput = components['schemas']['StrategyUpdate']
export type StrategyStats = components['schemas']['StrategyStats']
export type StrategyStatus = components['schemas']['StrategyStatus']
export type Timeframe = components['schemas']['Timeframe']
export type MarketType = components['schemas']['MarketType']
export type Priority = components['schemas']['Priority']

export type StrategyCode = components['schemas']['StrategyCodeRead']
export type StrategyCodeUpdateInput = components['schemas']['StrategyCodeUpdate']
export type StrategyCodeValidateInput = components['schemas']['StrategyCodeValidateRequest']
export type StrategyValidationResult = components['schemas']['StrategyValidationResult']
export type SyntaxErrorDetail = components['schemas']['SyntaxErrorDetail']

export type StrategySort = 'updated_at' | 'name'
export type SortOrder = 'asc' | 'desc'

export interface StrategyListParams {
  q?: string
  status?: StrategyStatus
  sort?: StrategySort
  order?: SortOrder
  limit?: number
  offset?: number
  [key: string]: string | number | boolean | undefined | null
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export const STRATEGY_STATUSES: StrategyStatus[] = [
  'draft',
  'testing',
  'validated',
  'archived',
  'rejected',
]

export const TIMEFRAMES: Timeframe[] = [
  '1m',
  '3m',
  '5m',
  '15m',
  '30m',
  '1h',
  '2h',
  '4h',
  '1d',
  '1w',
]

export const MARKET_TYPES: MarketType[] = ['equity', 'futures', 'options', 'fx', 'crypto', 'index']

export const PRIORITIES: Priority[] = ['low', 'medium', 'high']

// Mirrors app/services/strategy_code_service.py DEFAULT_STRATEGY_TEMPLATE - the
// "Reset to Template" button restores this without a round trip to the server.
export const DEFAULT_STRATEGY_TEMPLATE = `class Strategy:

    def on_start(self):
        pass

    def on_bar(self, bar):
        pass

    def on_stop(self):
        pass
`
