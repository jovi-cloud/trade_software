import type { components } from '@/types/api'

export type BacktestRunStatus = 'completed' | 'failed'

export type BacktestRunListItem = components['schemas']['BacktestRunListItem'] & {
  dataset_version_number?: number | null
}

export type BacktestRun = components['schemas']['BacktestRunRead'] & {
  dataset_version_id?: string | null
  dataset_version_number?: number | null
  dataset_import_id?: string | null
  dataset_imported_at?: string | null
  dataset_quality_score?: number | null
}
export type BacktestRunResearchInput = components['schemas']['BacktestRunResearchUpdate']
export type BacktestRunResearchTimeline = components['schemas']['BacktestRunResearchTimeline']

export type BacktestRunSortField =
  | 'created_at'
  | 'execution_completed_at'
  | 'net_profit'
  | 'trade_count'
  | 'total_return_pct'
  | 'cagr_pct'
  | 'max_drawdown_pct'
  | 'sharpe'
  | 'sortino'
  | 'calmar'
  | 'profit_factor'
  | 'win_rate_pct'
  | 'expectancy'
  | 'exposure_pct'

export type BacktestRunListParams = {
  q?: string
  strategy_id?: string
  dataset_id?: string
  status?: BacktestRunStatus
  date_from?: string
  date_to?: string
  sort?: BacktestRunSortField
  order?: 'asc' | 'desc'
  limit?: number
  offset?: number
}

export const BACKTEST_RUN_STATUSES: BacktestRunStatus[] = ['completed', 'failed']
