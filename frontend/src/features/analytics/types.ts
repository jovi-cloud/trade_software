import type { components } from '@/types/api'

export type AnalyticsReport = components['schemas']['AnalyticsReportRead']
export type MetricValue = components['schemas']['MetricValueRead']
export type MetricCategory = components['schemas']['MetricCategory']
export type MetricFormat = components['schemas']['MetricFormat']
export type MonthlyReturn = components['schemas']['MonthlyReturnRead']
export type YearlyReturn = components['schemas']['YearlyReturnRead']
export type DrawdownPoint = components['schemas']['DrawdownPointRead']
export type EquityCurvePoint = components['schemas']['EquityCurvePointRead']

export type AnalyticsSection =
  | 'overview'
  | 'returns'
  | 'risk'
  | 'risk_adjusted'
  | 'trades'
  | 'portfolio'
  | 'statistics'
  | 'monthly'
  | 'yearly'
  | 'drawdown'
  | 'equity'

export const ANALYTICS_SECTIONS: { id: AnalyticsSection; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'returns', label: 'Returns' },
  { id: 'risk', label: 'Risk' },
  { id: 'risk_adjusted', label: 'Risk-adjusted' },
  { id: 'trades', label: 'Trades' },
  { id: 'portfolio', label: 'Portfolio' },
  { id: 'statistics', label: 'Statistics' },
  { id: 'monthly', label: 'Monthly Returns' },
  { id: 'yearly', label: 'Yearly Returns' },
  { id: 'drawdown', label: 'Drawdown' },
  { id: 'equity', label: 'Equity' },
]
