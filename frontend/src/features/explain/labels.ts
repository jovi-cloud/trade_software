import type { components } from '@/types/api'

type ExplainEventRead = components['schemas']['ExplainEventRead']
type ExplainLayer = ExplainEventRead['layer']
type ExplainLevel = components['schemas']['ExplainLevel']

export const EXPLAIN_LAYER_LABELS: Record<ExplainLayer, string> = {
  system: 'System',
  execution: 'Execution',
  decision: 'Strategy Decision',
  narrative: 'Summary',
}

export const EXPLAIN_EVENT_LABELS: Record<ExplainEventRead['event_type'], string> = {
  run_started: 'Run Started',
  dataset_loaded: 'Dataset Loaded',
  strategy_loaded: 'Strategy Loaded',
  parameters_applied: 'Parameters Applied',
  bar_processing_started: 'Bar Processing',
  signal_generated: 'Signal Generated',
  order_created: 'Order Created',
  order_submitted: 'Order Submitted',
  order_filled: 'Order Filled',
  order_rejected: 'Order Rejected',
  position_opened: 'Position Opened',
  position_updated: 'Position Updated',
  position_closed: 'Position Closed',
  profit_calculated: 'Profit Calculated',
  conditions_evaluated: 'Conditions Evaluated',
  metrics_generated: 'Metrics Generated',
  charts_generated: 'Charts Generated',
  run_completed: 'Run Completed',
  human_narrative: 'Activity',
}

export const EXPLAIN_LEVEL_LABELS: Record<ExplainLevel, string> = {
  none: 'Off',
  trades_only: 'Trades',
  full: 'Full Detail',
}

export const REASON_CODE_LABELS: Record<string, string> = {
  'signal.long': 'Long Entry Signal',
  'signal.short': 'Short Entry Signal',
  'signal.exit': 'Exit Signal',
  'signal.rejected': 'Signal Rejected',
  'order.created': 'Order Created',
  'order.submitted': 'Order Submitted',
  'order.filled': 'Order Filled',
  'order.cancelled': 'Order Cancelled',
  'order.rejected': 'Order Rejected',
  'position.opened': 'Position Opened',
  'position.updated': 'Position Updated',
  'position.closed': 'Position Closed',
  'risk.insufficient_cash': 'Insufficient Cash',
  'risk.max_position': 'Position Limit',
  'risk.validation_failed': 'Validation Failed',
  'system.run_started': 'Run Started',
  'system.dataset_loaded': 'Dataset Loaded',
  'system.strategy_loaded': 'Strategy Loaded',
  'system.parameters_loaded': 'Parameters Loaded',
  'system.metrics_generated': 'Metrics Generated',
  'system.completed': 'Run Completed',
  'system.profit_calculated': 'Profit Calculated',
  'decision.conditions_evaluated': 'Conditions Evaluated',
  'decision.no_trade': 'No Trade',
}

export const STATUS_LABELS: Record<ExplainEventRead['status'], string> = {
  ok: 'OK',
  info: 'Info',
  warning: 'Warning',
  rejected: 'Rejected',
  failed: 'Failed',
}

export const TRADE_OUTCOME_LABELS: Record<
  components['schemas']['TradeOutcome'],
  string
> = {
  winning: 'Winning',
  losing: 'Losing',
  break_even: 'Break Even',
}

export function formatReasonCode(code: string): string {
  return REASON_CODE_LABELS[code] ?? code.replace(/\./g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

export function formatOrderType(orderType: string): string {
  switch (orderType) {
    case 'buy_market':
      return 'Buy'
    case 'sell_market':
      return 'Sell Short'
    case 'close':
      return 'Close'
    default:
      return orderType
  }
}

export function formatOrderStatus(status: string): string {
  switch (status) {
    case 'filled':
      return 'Filled'
    case 'rejected':
      return 'Rejected'
    case 'pending':
      return 'Pending'
    default:
      return status
  }
}

export function formatTradeSide(side: string): string {
  return side === 'long' ? 'Long' : 'Short'
}

export function formatTradeNumber(tradeId: number | null | undefined): string {
  if (tradeId === null || tradeId === undefined) return '—'
  return `Trade ${tradeId}`
}

export function formatOrderRef(orderId: number | null | undefined): string {
  if (orderId === null || orderId === undefined) return '—'
  return `Order ${orderId}`
}

export function formatPositionRef(positionId: number | null | undefined): string {
  if (positionId === null || positionId === undefined) return '—'
  return `Position ${positionId}`
}
