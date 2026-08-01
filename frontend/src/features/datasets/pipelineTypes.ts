import type { components } from '@/types/api'

export type PipelineReport = components['schemas']['PipelineReportRead']
export type PipelineValidation = components['schemas']['DatasetValidationReport']
export type PipelineSession = components['schemas']['SessionReportRead'] & {
  unexpected_weekend_samples?: string[]
  unexpected_holiday_samples?: string[]
}
export type PipelineGaps = components['schemas']['GapReportRead']
export type PipelinePriceAnomalies = components['schemas']['PriceAnomalyReportRead']
