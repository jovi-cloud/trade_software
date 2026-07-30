import type { components } from '@/types/api'

export type LibraryStrategyListItem = components['schemas']['LibraryStrategyListItem']
export type LibraryStrategy = components['schemas']['LibraryStrategyRead']
export type LibraryFacets = components['schemas']['LibraryFacetsRead']
export type ParamSpec = components['schemas']['ParamSpecRead']
export type ParamGroup = components['schemas']['ParamGroupRead']
export type ParamValidation = components['schemas']['ParamValidationRead']
export type StrategyDocumentation = components['schemas']['StrategyDocumentationRead']
export type StrategyCategory = components['schemas']['StrategyCategory']
export type RiskLevel = components['schemas']['RiskLevel']
export type TradingStyle = 'intraday' | 'swing' | 'position'

export type ParamValue = boolean | number | string

export interface LibraryListParams {
  q?: string
  category?: StrategyCategory
  tag?: string[]
  market?: string
  timeframe?: string
  risk_level?: RiskLevel
  style?: TradingStyle
  valid_only?: boolean
  limit?: number
  offset?: number
  [key: string]: string | number | boolean | string[] | undefined | null
}

export interface ValidateParamsInput {
  params: Record<string, ParamValue>
}
