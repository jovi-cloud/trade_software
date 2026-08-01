/**
 * Display formatting. Numbers, dates and durations must look identical
 * everywhere in the application, so they are formatted only here.
 */

const PLACEHOLDER = '--'

/** Percent values arrive from the API already scaled: 12.5 means 12.5%. */
export function formatPercent(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return PLACEHOLDER
  return `${value.toFixed(digits)}%`
}

export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return PLACEHOLDER
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function formatCurrency(
  value: number | null | undefined,
  currency = 'INR',
  digits = 2,
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return PLACEHOLDER
  return value.toLocaleString(undefined, {
    style: 'currency',
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

export function formatInteger(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return PLACEHOLDER
  return Math.round(value).toLocaleString()
}

/** Exchange timezone bar data is displayed in, regardless of viewer's local timezone. */
export const DEFAULT_EXCHANGE_TIMEZONE = 'Asia/Kolkata'

/** Bar timestamps are int64 UTC epoch milliseconds; shown in the dataset's exchange timezone. */
export function formatTimestamp(
  epochMs: number | null | undefined,
  timeZone: string = DEFAULT_EXCHANGE_TIMEZONE,
): string {
  if (epochMs === null || epochMs === undefined) return PLACEHOLDER
  return new Date(epochMs).toLocaleString('en-IN', { timeZone })
}

export function formatDate(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return PLACEHOLDER
  return new Date(value).toLocaleDateString()
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return PLACEHOLDER
  if (ms < 1000) return `${Math.round(ms)}ms`

  const totalSeconds = Math.floor(ms / 1000)
  const seconds = totalSeconds % 60
  const minutes = Math.floor(totalSeconds / 60) % 60
  const hours = Math.floor(totalSeconds / 3600)

  if (hours > 0) return `${hours}h ${minutes}m`
  if (minutes > 0) return `${minutes}m ${seconds}s`
  return `${seconds}s`
}
