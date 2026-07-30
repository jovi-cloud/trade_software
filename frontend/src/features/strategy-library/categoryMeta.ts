import type { RiskLevel, StrategyCategory } from './types'

const CATEGORY_LABELS: Record<StrategyCategory, string> = {
  trend_following: 'Trend following',
  mean_reversion: 'Mean reversion',
  breakout: 'Breakout',
  momentum: 'Momentum',
  volatility: 'Volatility',
  volume: 'Volume',
}

const RISK_LABELS: Record<RiskLevel, string> = {
  low: 'Low risk',
  medium: 'Medium risk',
  high: 'High risk',
}

const RISK_CLASSES: Record<RiskLevel, string> = {
  low: 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-400',
  medium: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
  high: 'bg-rose-500/10 text-rose-700 dark:text-rose-400',
}

export function categoryLabel(category: StrategyCategory): string {
  return CATEGORY_LABELS[category] ?? category
}

export function riskLabel(risk: RiskLevel): string {
  return RISK_LABELS[risk] ?? risk
}

export function riskClassName(risk: RiskLevel): string {
  return RISK_CLASSES[risk] ?? ''
}

export function humanise(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}
