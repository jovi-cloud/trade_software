import type { PipelineGaps, PipelineReport, PipelineSession, PipelinePriceAnomalies } from './pipelineTypes'

export interface QualityDeduction {
  key: string
  label: string
  count: number | null
  countLabel: string
  formula: string
  maxCap: number
  deduction: number
  samples?: readonly string[]
}

export interface QualityScoreBreakdown {
  startingScore: number
  deductions: QualityDeduction[]
  totalDeducted: number
  finalScore: number
}

function cappedDeduction(raw: number, max: number): number {
  return Math.min(max, raw)
}

function rowRate(count: number, total: number, multiplier: number, max: number): number {
  if (total <= 0) return 0
  return cappedDeduction((count / total) * 100 * multiplier, max)
}

function sessionIssues(session: PipelineSession): number {
  return (
    session.missing_opening_candles +
    session.missing_closing_candles +
    session.candles_outside_session +
    session.unexpected_weekend_bars +
    session.unexpected_holiday_bars
  )
}

export function computeQualityBreakdown(
  pipeline: PipelineReport | null | undefined,
): QualityScoreBreakdown | null {
  if (!pipeline) return null

  const validation = pipeline.validation
  const session: PipelineSession = pipeline.session ?? {
    missing_opening_candles: 0,
    missing_closing_candles: 0,
    candles_outside_session: 0,
    unexpected_weekend_bars: 0,
    unexpected_holiday_bars: 0,
    missing_opening_samples: [],
    missing_closing_samples: [],
    outside_session_samples: [],
    unexpected_weekend_samples: [],
    unexpected_holiday_samples: [],
  }
  const gaps = pipeline.gaps
  const total = Math.max(validation.total_rows, 1)

  if (validation.valid_rows === 0) {
    return {
      startingScore: 100,
      deductions: [
        {
          key: 'no_valid_rows',
          label: 'No valid rows',
          count: 0,
          countLabel: 'valid rows',
          formula: 'Score forced to 0',
          maxCap: 100,
          deduction: 100,
        },
      ],
      totalDeducted: 100,
      finalScore: 0,
    }
  }

  if (pipeline.timeframe && !pipeline.timeframe.is_consistent) {
    const deduction = 100 - pipeline.quality_score
    return {
      startingScore: 100,
      deductions: [
        {
          key: 'inconsistent_timeframe',
          label: 'Inconsistent bar intervals',
          count: pipeline.timeframe.inconsistent_intervals,
          countLabel: 'inconsistent intervals',
          formula: 'Score capped below reject threshold',
          maxCap: 100,
          deduction,
        },
      ],
      totalDeducted: deduction,
      finalScore: pipeline.quality_score,
    }
  }

  const issues = sessionIssues(session)
  const deductions: QualityDeduction[] = [
    {
      key: 'invalid_dates',
      label: 'Invalid dates',
      count: validation.invalid_dates,
      countLabel: 'rows',
      formula: '(count / total_rows) × 150',
      maxCap: 15,
      deduction: rowRate(validation.invalid_dates, total, 1.5, 15),
    },
    {
      key: 'invalid_prices',
      label: 'Invalid prices',
      count: validation.invalid_prices,
      countLabel: 'rows',
      formula: '(count / total_rows) × 100',
      maxCap: 10,
      deduction: rowRate(validation.invalid_prices, total, 1, 10),
    },
    {
      key: 'ohlc_violations',
      label: 'OHLC violations',
      count: validation.ohlc_violations,
      countLabel: 'rows',
      formula: '(count / total_rows) × 200',
      maxCap: 20,
      deduction: rowRate(validation.ohlc_violations, total, 2, 20),
    },
    {
      key: 'negative_volumes',
      label: 'Negative volumes',
      count: validation.negative_volumes,
      countLabel: 'rows',
      formula: '(count / total_rows) × 100',
      maxCap: 10,
      deduction: rowRate(validation.negative_volumes, total, 1, 10),
    },
    {
      key: 'non_positive_prices',
      label: 'Non-positive prices',
      count: validation.non_positive_prices,
      countLabel: 'rows',
      formula: '(count / total_rows) × 150',
      maxCap: 15,
      deduction: rowRate(validation.non_positive_prices, total, 1.5, 15),
    },
    {
      key: 'duplicate_timestamps',
      label: 'Duplicate timestamps',
      count: validation.duplicate_timestamps,
      countLabel: 'rows',
      formula: '(count / total_rows) × 50',
      maxCap: 5,
      deduction: rowRate(validation.duplicate_timestamps, total, 0.5, 5),
      samples: validation.duplicate_samples,
    },
    {
      key: 'nan_values',
      label: 'NaN values',
      count: validation.nan_values,
      countLabel: 'rows',
      formula: '(count / total_rows) × 100',
      maxCap: 5,
      deduction: rowRate(validation.nan_values, total, 1, 5),
    },
    {
      key: 'infinity_values',
      label: 'Infinity values',
      count: validation.infinity_values,
      countLabel: 'rows',
      formula: '(count / total_rows) × 100',
      maxCap: 5,
      deduction: rowRate(validation.infinity_values, total, 1, 5),
    },
    {
      key: 'gap_percentage',
      label: 'Gap %',
      count: gaps?.gap_percentage ?? null,
      countLabel: 'gap %',
      formula: 'gap_percentage × 0.3',
      maxCap: 15,
      deduction: cappedDeduction((gaps?.gap_percentage ?? 0) * 0.3, 15),
      samples: gaps?.missing_details,
    },
    {
      key: 'session_issues',
      label: 'Session issues',
      count: issues,
      countLabel: 'issues',
      formula: 'total_issues × 0.2',
      maxCap: 10,
      deduction: cappedDeduction(issues * 0.2, 10),
    },
    {
      key: 'out_of_order',
      label: 'Out-of-order timestamps',
      count: validation.out_of_order_timestamps,
      countLabel: 'rows',
      formula: 'Flat −1 if any',
      maxCap: 1,
      deduction: validation.out_of_order_timestamps > 0 ? 1 : 0,
    },
  ]

  const totalDeducted = deductions.reduce((sum, item) => sum + item.deduction, 0)
  const finalScore = Math.max(0, Math.min(100, Math.round(100 - totalDeducted)))

  return {
    startingScore: 100,
    deductions,
    totalDeducted,
    finalScore,
  }
}

export const SESSION_ISSUE_SLICE_COLORS = [
  '#dc2626',
  '#d97706',
  '#2563eb',
  '#7c3aed',
  '#0891b2',
] as const

export function sessionIssueRows(session: PipelineSession): Array<{
  key: string
  label: string
  count: number
  color: string
  samples?: readonly string[]
}> {
  const rows = [
    {
      key: 'missing_opening',
      label: 'Missing opening candles',
      count: session.missing_opening_candles,
      samples: session.missing_opening_samples,
    },
    {
      key: 'missing_closing',
      label: 'Missing closing candles',
      count: session.missing_closing_candles,
      samples: session.missing_closing_samples,
    },
    {
      key: 'outside_session',
      label: 'Candles outside session',
      count: session.candles_outside_session,
      samples: session.outside_session_samples,
    },
    {
      key: 'weekend',
      label: 'Unexpected weekend bars',
      count: session.unexpected_weekend_bars,
      samples: session.unexpected_weekend_samples,
    },
    {
      key: 'holiday',
      label: 'Unexpected holiday bars',
      count: session.unexpected_holiday_bars,
      samples: session.unexpected_holiday_samples,
    },
  ]

  return rows.map((row, index) => ({
    ...row,
    color: SESSION_ISSUE_SLICE_COLORS[index % SESSION_ISSUE_SLICE_COLORS.length] ?? '#2563eb',
  }))
}

export function gapDetailRows(gaps: PipelineGaps | null | undefined): Array<{
  label: string
  count: number | string
}> {
  if (!gaps) return []
  return [
    { label: 'Expected bars', count: gaps.expected_bars },
    { label: 'Actual bars', count: gaps.actual_bars },
    { label: 'Missing bars', count: gaps.missing_bars },
    { label: 'Duplicate bars', count: gaps.duplicate_bars },
    { label: 'Large jumps', count: gaps.large_jumps },
    { label: 'Partial trading days', count: gaps.partial_trading_days },
    { label: 'Gap %', count: gaps.gap_percentage },
  ]
}

export function priceAnomalyRows(
  anomalies: PipelinePriceAnomalies | null | undefined,
): Array<{
  key: string
  label: string
  count: number
  barCount: number
  dayCount: number
  samples?: readonly string[]
  daySamples?: readonly string[]
}> {
  if (!anomalies) return []
  return [
    {
      key: 'intraday_spikes_over_10',
      label: 'Intraday price spikes >10%',
      count: anomalies.spikes_over_10_pct,
      barCount: anomalies.intraday_bars_on_days_over_10_pct,
      dayCount: anomalies.intraday_days_over_10_samples?.length ?? 0,
      samples: anomalies.spike_over_10_samples,
      daySamples: anomalies.intraday_days_over_10_samples,
    },
    {
      key: 'intraday_spikes_over_20',
      label: 'Intraday price spikes >20%',
      count: anomalies.spikes_over_20_pct,
      barCount: anomalies.intraday_bars_on_days_over_20_pct,
      dayCount: anomalies.intraday_days_over_20_samples?.length ?? 0,
      samples: anomalies.spike_over_20_samples,
      daySamples: anomalies.intraday_days_over_20_samples,
    },
    {
      key: 'cross_day_spikes_over_10',
      label: 'Overnight gaps between days >10%',
      count: anomalies.cross_day_spikes_over_10_pct,
      barCount: anomalies.cross_day_bars_on_days_over_10_pct,
      dayCount: anomalies.cross_day_days_over_10_samples?.length ?? 0,
      samples: anomalies.cross_day_spike_over_10_samples,
      daySamples: anomalies.cross_day_days_over_10_samples,
    },
    {
      key: 'cross_day_spikes_over_20',
      label: 'Overnight gaps between days >20%',
      count: anomalies.cross_day_spikes_over_20_pct,
      barCount: anomalies.cross_day_bars_on_days_over_20_pct,
      dayCount: anomalies.cross_day_days_over_20_samples?.length ?? 0,
      samples: anomalies.cross_day_spike_over_20_samples,
      daySamples: anomalies.cross_day_days_over_20_samples,
    },
  ]
}

const REMOVABLE_SESSION_KEYS = new Set(['outside_session', 'weekend', 'holiday'])

export function hasRemovableDatasetIssues(
  pipeline: PipelineReport | null | undefined,
): boolean {
  if (!pipeline) return false

  const session = pipeline.session
  const hasRemovableSessionIssues =
    session !== undefined &&
    sessionIssueRows(session).some(
      (row) => REMOVABLE_SESSION_KEYS.has(row.key) && row.count > 0,
    )
  const hasRemovableAnomalyDays = priceAnomalyRows(pipeline.price_anomalies).some(
    (row) => row.dayCount > 0 || row.count > 0,
  )

  return hasRemovableSessionIssues || hasRemovableAnomalyDays
}
