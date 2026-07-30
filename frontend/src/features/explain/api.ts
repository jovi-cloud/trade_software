import { api } from '@/lib/apiClient'

import type { components } from '@/types/api'

export type ExplainEvent = components['schemas']['ExplainEventRead']
export type TradeInspection = components['schemas']['TradeInspectionRead']
export type TradeSummary = components['schemas']['TradeSummaryRead']

export interface ExplainEventListParams {
  layer?: ExplainEvent['layer']
  event_type?: ExplainEvent['event_type']
  trade_id?: number
  order_id?: number
  position_id?: number
  reason_code?: string
  status?: ExplainEvent['status']
  q?: string
  timestamp_from_ms?: number
  timestamp_to_ms?: number
  bar_index?: number
  sort?: 'seq' | 'timestamp_ms' | 'bar_index' | 'event_type'
  order?: 'asc' | 'desc'
  limit?: number
  offset?: number
}

interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export function fetchRunEvents(
  runId: string,
  params: ExplainEventListParams,
): Promise<Page<ExplainEvent>> {
  return api.get<Page<ExplainEvent>>(`/backtests/runs/${runId}/events`, {
    params: params as Record<string, string | number | boolean | null | undefined>,
  })
}

export function fetchTradeInspection(
  runId: string,
  tradeId: number,
): Promise<TradeInspection> {
  return api.get<TradeInspection>(`/backtests/runs/${runId}/trades/${tradeId}`)
}

export function fetchTradeEvents(
  runId: string,
  tradeId: number,
  params: { limit?: number; offset?: number },
): Promise<Page<ExplainEvent>> {
  return api.get<Page<ExplainEvent>>(`/backtests/runs/${runId}/trades/${tradeId}/events`, {
    params,
  })
}

export type BarInspection = components['schemas']['BarInspectionRead']

export function fetchBarInspection(runId: string, barIndex: number): Promise<BarInspection> {
  return api.get<BarInspection>(`/backtests/runs/${runId}/bars/${barIndex}`)
}

export function fetchBarEvents(
  runId: string,
  barIndex: number,
  params: { limit?: number; offset?: number },
): Promise<Page<ExplainEvent>> {
  return api.get<Page<ExplainEvent>>(`/backtests/runs/${runId}/bars/${barIndex}/events`, {
    params,
  })
}

export type DecisionLog = components['schemas']['DecisionLogRead']
export type DecisionRow = components['schemas']['DecisionRowRead']
export type DecisionSchema = components['schemas']['DecisionSchemaRead']
export type DecisionSummary = components['schemas']['DecisionSummaryRead']
export type Operand = components['schemas']['OperandRead']

/** The decision log is uncapped, so it is always read a window at a time. */
export function fetchDecisions(
  runId: string,
  params: { start: number; count: number },
): Promise<DecisionLog> {
  return api.get<DecisionLog>(`/backtests/runs/${runId}/decisions`, { params })
}

export function fetchDecisionSummary(runId: string): Promise<DecisionSummary> {
  return api.get<DecisionSummary>(`/backtests/runs/${runId}/decisions/summary`)
}
