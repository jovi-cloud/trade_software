import type { components } from '@/types/api'

export type ComparisonReport = components['schemas']['ComparisonReportRead']
export type MetricComparisonRow = components['schemas']['MetricComparisonRowRead']
export type ResearchInsight = components['schemas']['ResearchInsightRead']
export type ComparedRunSummary = components['schemas']['ComparedRunSummaryRead']
export type MetricCategory = components['schemas']['MetricCategory']

export type ComparisonSection =
  | 'overview'
  | 'returns'
  | 'risk'
  | 'risk_adjusted'
  | 'trades'
  | 'portfolio'
  | 'statistics'
  | 'dataset'
  | 'strategy'
  | 'execution'
  | 'equity'
  | 'drawdown'
  | 'monthly'
  | 'insights'

export const COMPARISON_SECTIONS: { id: ComparisonSection; label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'insights', label: 'Insights' },
  { id: 'returns', label: 'Returns' },
  { id: 'risk', label: 'Risk' },
  { id: 'risk_adjusted', label: 'Risk-adjusted' },
  { id: 'trades', label: 'Trades' },
  { id: 'portfolio', label: 'Portfolio' },
  { id: 'statistics', label: 'Statistics' },
  { id: 'dataset', label: 'Dataset' },
  { id: 'strategy', label: 'Strategy' },
  { id: 'execution', label: 'Execution' },
  { id: 'equity', label: 'Equity' },
  { id: 'drawdown', label: 'Drawdown' },
  { id: 'monthly', label: 'Monthly Returns' },
]

export const RUN_COLORS = [
  '#2563eb',
  '#dc2626',
  '#16a34a',
  '#d97706',
  '#7c3aed',
  '#0891b2',
  '#db2777',
  '#65a30d',
  '#ea580c',
  '#4f46e5',
] as const
