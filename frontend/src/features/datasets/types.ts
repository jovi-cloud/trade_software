import type { components } from '@/types/api'

export type Dataset = components['schemas']['DatasetRead']
export type DatasetValidationReport = components['schemas']['DatasetValidationReport']
export type DatasetPreview = components['schemas']['DatasetPreview']
export type BarRow = components['schemas']['BarRow']
export type ImportStatus = components['schemas']['ImportStatus']
export type Timeframe = components['schemas']['Timeframe']

export type DatasetSort = 'updated_at' | 'name' | 'row_count'
export type SortOrder = 'asc' | 'desc'
export type PreviewPart = 'head' | 'tail'

export interface DatasetListParams {
  q?: string
  timeframe?: Timeframe
  sort?: DatasetSort
  order?: SortOrder
  limit?: number
  offset?: number
  [key: string]: string | number | boolean | undefined | null
}

export interface DatasetImportInput {
  name: string
  symbol: string
  exchange: string
  timeframe: Timeframe
  file: File
}

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

/** The columns a CSV must provide, shown in the import instructions. */
export const REQUIRED_CSV_COLUMNS = ['timestamp', 'open', 'high', 'low', 'close', 'volume'] as const
