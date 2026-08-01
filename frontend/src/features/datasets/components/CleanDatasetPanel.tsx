import { useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { formatInteger } from '@/lib/format'

import { priceAnomalyRows, sessionIssueRows } from '../qualityScore'
import type { PipelineReport } from '../pipelineTypes'
import type { DatasetCleanInput } from '../types'
import { SessionIssueDetailRow } from './SessionIssueDetailRow'

type RemovableKey =
  | 'remove_outside_session'
  | 'remove_weekend_bars'
  | 'remove_holiday_bars'
  | 'remove_intraday_spike_days_over_10pct'
  | 'remove_intraday_spike_days_over_20pct'
  | 'remove_cross_day_spike_days_over_10pct'
  | 'remove_cross_day_spike_days_over_20pct'

const REMOVABLE_BY_SESSION_KEY: Record<string, RemovableKey> = {
  outside_session: 'remove_outside_session',
  weekend: 'remove_weekend_bars',
  holiday: 'remove_holiday_bars',
}

const REMOVABLE_BY_ANOMALY_KEY: Record<string, RemovableKey> = {
  intraday_spikes_over_10: 'remove_intraday_spike_days_over_10pct',
  intraday_spikes_over_20: 'remove_intraday_spike_days_over_20pct',
  cross_day_spikes_over_10: 'remove_cross_day_spike_days_over_10pct',
  cross_day_spikes_over_20: 'remove_cross_day_spike_days_over_20pct',
}

const GAP_DETAIL_NOTE =
  'These are absent bars in the feed, not extra rows. Cleaning cannot remove data gaps — re-validate after re-import or accept partial trading days.'

interface CleanDatasetPanelProps {
  datasetId: string
  pipeline: PipelineReport | null | undefined
  sessionOpen?: string
  sessionClose?: string
  isCleaning: boolean
  onClean: (input: DatasetCleanInput) => void
}
export function CleanDatasetPanel({
  datasetId,
  pipeline,
  sessionOpen = '09:15',
  sessionClose = '15:25',
  isCleaning,
  onClean,
}: CleanDatasetPanelProps) {
  const sessionRows = useMemo(
    () => (pipeline?.session ? sessionIssueRows(pipeline.session) : []),
    [pipeline?.session],
  )
  const anomalyRows = useMemo(
    () => priceAnomalyRows(pipeline?.price_anomalies),
    [pipeline?.price_anomalies],
  )

  const removableSessionRows = sessionRows.filter((row) => REMOVABLE_BY_SESSION_KEY[row.key])
  const removableAnomalyRows = anomalyRows.filter(
    (row) => REMOVABLE_BY_ANOMALY_KEY[row.key] && row.dayCount > 0,
  )
  const gapRows = sessionRows.filter((row) => !REMOVABLE_BY_SESSION_KEY[row.key])

  const [selected, setSelected] = useState<Record<RemovableKey, boolean>>(() => ({
    remove_outside_session: (sessionRows.find((row) => row.key === 'outside_session')?.count ?? 0) > 0,
    remove_weekend_bars: (sessionRows.find((row) => row.key === 'weekend')?.count ?? 0) > 0,
    remove_holiday_bars: (sessionRows.find((row) => row.key === 'holiday')?.count ?? 0) > 0,
    remove_intraday_spike_days_over_10pct:
      (anomalyRows.find((row) => row.key === 'intraday_spikes_over_10')?.dayCount ?? 0) > 0,
    remove_intraday_spike_days_over_20pct:
      (anomalyRows.find((row) => row.key === 'intraday_spikes_over_20')?.dayCount ?? 0) > 0,
    remove_cross_day_spike_days_over_10pct:
      (anomalyRows.find((row) => row.key === 'cross_day_spikes_over_10')?.dayCount ?? 0) > 0,
    remove_cross_day_spike_days_over_20pct:
      (anomalyRows.find((row) => row.key === 'cross_day_spikes_over_20')?.dayCount ?? 0) > 0,
  }))

  const selectedRemovalCount =
    removableSessionRows.reduce((sum, row) => {
      const optionKey = REMOVABLE_BY_SESSION_KEY[row.key]
      if (!optionKey || !selected[optionKey]) return sum
      return sum + row.count
    }, 0) +
    removableAnomalyRows.reduce((sum, row) => {
      const optionKey = REMOVABLE_BY_ANOMALY_KEY[row.key]
      if (!optionKey || !selected[optionKey]) return sum
      return sum + row.barCount
    }, 0)

  const canClean = selectedRemovalCount > 0 && !isCleaning

  return (
    <div className="rounded-lg border border-border bg-muted/20 p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium">Remove corrupt bars</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Session {sessionOpen}–{sessionClose} (last bar open time). Creates a new immutable
            dataset version with the selected violations removed. Missing opening/closing candles
            are gaps, not extra rows, so they cannot be deleted. Price anomaly cleaning removes
            all bars on affected trading days.
          </p>
        </div>
        <Button
          type="button"
          variant="destructive"
          size="sm"
          disabled={!canClean}
          onClick={() =>
            onClean({
              remove_outside_session: selected.remove_outside_session,
              remove_weekend_bars: selected.remove_weekend_bars,
              remove_holiday_bars: selected.remove_holiday_bars,
              remove_intraday_spike_days_over_10pct:
                selected.remove_intraday_spike_days_over_10pct,
              remove_intraday_spike_days_over_20pct:
                selected.remove_intraday_spike_days_over_20pct,
              remove_cross_day_spike_days_over_10pct:
                selected.remove_cross_day_spike_days_over_10pct,
              remove_cross_day_spike_days_over_20pct:
                selected.remove_cross_day_spike_days_over_20pct,
            })
          }
        >
          {isCleaning ? 'Cleaning…' : `Remove ${formatInteger(selectedRemovalCount)} bars`}
        </Button>
      </div>

      <ul className="space-y-2 text-sm">
        {removableSessionRows.map((row) => {
          const optionKey = REMOVABLE_BY_SESSION_KEY[row.key]
          if (!optionKey) return null
          return (
            <li
              key={row.key}
              className="flex items-start gap-3 rounded-md border border-border/60 bg-background px-3 py-2"
            >
              <input
                id={`${datasetId}-${row.key}`}
                type="checkbox"
                className="mt-1"
                checked={selected[optionKey]}
                disabled={row.count === 0 || isCleaning}
                onChange={(event) =>
                  setSelected((current) => ({
                    ...current,
                    [optionKey]: event.target.checked,
                  }))
                }
              />
              <label htmlFor={`${datasetId}-${row.key}`} className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">{row.label}</span>
                  <span className="tabular text-muted-foreground">
                    {formatInteger(row.count)}
                  </span>
                </div>
              </label>
            </li>
          )
        })}
        {removableAnomalyRows.map((row) => {
          const optionKey = REMOVABLE_BY_ANOMALY_KEY[row.key]
          if (!optionKey) return null
          return (
            <li
              key={row.key}
              className="flex items-start gap-3 rounded-md border border-border/60 bg-background px-3 py-2"
            >
              <input
                id={`${datasetId}-${row.key}`}
                type="checkbox"
                className="mt-1"
                checked={selected[optionKey]}
                disabled={row.dayCount === 0 || isCleaning}
                onChange={(event) =>
                  setSelected((current) => ({
                    ...current,
                    [optionKey]: event.target.checked,
                  }))
                }
              />
              <label htmlFor={`${datasetId}-${row.key}`} className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">Remove days with {row.label.toLowerCase()}</span>
                  <span className="tabular text-muted-foreground">
                    {formatInteger(row.barCount)} bars / {formatInteger(row.dayCount)} days
                  </span>
                </div>
                {row.daySamples && row.daySamples.length > 0 && (
                  <p className="mt-1 text-xs text-muted-foreground">
                    {row.daySamples.join(', ')}
                  </p>
                )}
              </label>
            </li>
          )
        })}
      </ul>

      {gapRows.some((row) => row.count > 0) && (
        <div className="mt-4">
          <p className="mb-2 text-xs font-medium text-muted-foreground">Cannot remove (data gaps)</p>
          <ul className="space-y-2 text-sm">
            {gapRows
              .filter((row) => row.count > 0)
              .map((row) => (
                <SessionIssueDetailRow
                  key={row.key}
                  label={row.label}
                  count={row.count}
                  samples={row.samples}
                  detailNote={GAP_DETAIL_NOTE}
                  sampleLabel="expected bar"
                />
              ))}
          </ul>
        </div>
      )}
    </div>
  )
}
