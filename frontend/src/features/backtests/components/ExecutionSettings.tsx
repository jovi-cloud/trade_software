import { AlertTriangle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { priceAnomalyRows } from '@/features/datasets/qualityScore'
import type { PipelineReport } from '@/features/datasets/pipelineTypes'

import {
  DEFAULT_STOP_LOSS_ATR,
  DEFAULT_STOP_LOSS_PERCENT,
  explainabilityWarning,
  type ExplainLevel,
  type WorkflowState,
} from '../workflow'

interface ExecutionSettingsProps {
  state: WorkflowState
  /** The level the run will use, after the strategy's recommendation is applied. */
  explainLevel: ExplainLevel
  /** Whether the selected strategy traces conditions, for the downgrade warning. */
  supportsConditionTracing: boolean | undefined
  isRecommendedLevel: boolean
  /** Total bars in the selected dataset, when known. */
  datasetBarCount?: number
  pipelineReport?: PipelineReport | null
  sessionOpen?: string
  sessionClose?: string
  /** When false, stop-loss override controls are hidden. */
  showStopLossOverride?: boolean
  onChange: (patch: Partial<WorkflowState>) => void
}

const EXPLAIN_OPTIONS: { value: ExplainLevel; label: string; hint: string }[] = [
  { value: 'full', label: 'Full', hint: 'Every bar, condition and decision' },
  { value: 'trades_only', label: 'Trades only', hint: 'Orders, fills and trades' },
  { value: 'none', label: 'Off', hint: 'Fastest; no inspectors' },
]

export function ExecutionSettings({
  state,
  explainLevel,
  supportsConditionTracing,
  isRecommendedLevel,
  datasetBarCount,
  pipelineReport,
  sessionOpen,
  sessionClose,
  showStopLossOverride = true,
  onChange,
}: ExecutionSettingsProps) {
  const warning = explainabilityWarning(explainLevel, supportsConditionTracing)
  const anomalyRows = priceAnomalyRows(pipelineReport?.price_anomalies).filter(
    (row) => row.dayCount > 0 || row.count > 0,
  )
  const hasAnomalies = anomalyRows.length > 0

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-2">
          <Label htmlFor="capital">Initial capital</Label>
          <Input
            id="capital"
            type="number"
            min="0"
            step="any"
            value={state.initialCapital}
            onChange={(event) => onChange({ initialCapital: event.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="commission">Commission</Label>
          <Input
            id="commission"
            type="number"
            min="0"
            step="any"
            value={state.commission}
            onChange={(event) => onChange({ commission: event.target.value })}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="slippage">Slippage</Label>
          <Input
            id="slippage"
            type="number"
            min="0"
            step="any"
            value={state.slippage}
            onChange={(event) => onChange({ slippage: event.target.value })}
          />
        </div>
      </div>

      <div className="space-y-3 rounded-md border border-border p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium">Quick test on a subset</p>
            <p className="text-xs text-muted-foreground">
              Replay only the first N bars to validate logic before running the full dataset.
              {datasetBarCount !== undefined && datasetBarCount > 0
                ? ` This dataset has ${datasetBarCount.toLocaleString()} bars.`
                : ''}
            </p>
          </div>
          <Button
            type="button"
            variant={state.limitBars ? 'default' : 'outline'}
            size="sm"
            onClick={() => onChange({ limitBars: !state.limitBars })}
          >
            {state.limitBars ? 'Limited' : 'Full dataset'}
          </Button>
        </div>
        {state.limitBars && (
          <div className="space-y-2 sm:max-w-xs">
            <Label htmlFor="max-bars">Bars to replay</Label>
            <Input
              id="max-bars"
              type="number"
              min="1"
              step="1"
              value={state.maxBars}
              onChange={(event) => onChange({ maxBars: event.target.value })}
            />
          </div>
        )}
      </div>

      <div className="space-y-3 rounded-md border border-border p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium">Max trades per day</p>
            <p className="text-xs text-muted-foreground">
              Limit how many new positions can be opened on each exchange-local session day.
              Exits on open positions are still allowed.
            </p>
          </div>
          <Button
            type="button"
            variant={state.limitMaxTradesPerDay ? 'default' : 'outline'}
            size="sm"
            onClick={() => onChange({ limitMaxTradesPerDay: !state.limitMaxTradesPerDay })}
          >
            {state.limitMaxTradesPerDay ? 'Limited' : 'Unlimited'}
          </Button>
        </div>
        {state.limitMaxTradesPerDay && (
          <div className="space-y-2 sm:max-w-xs">
            <Label htmlFor="max-trades-per-day">New entries per day</Label>
            <Input
              id="max-trades-per-day"
              type="number"
              min="1"
              step="1"
              value={state.maxTradesPerDay}
              onChange={(event) => onChange({ maxTradesPerDay: event.target.value })}
            />
          </div>
        )}
      </div>

      <div className="space-y-3 rounded-md border border-border p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium">Trading time window</p>
            <p className="text-xs text-muted-foreground">
              Only open new positions between the start and end times in the dataset&apos;s
              exchange timezone. Exits on open positions are still allowed outside the window.
              {sessionOpen && sessionClose
                ? ` Dataset session is ${sessionOpen}–${sessionClose}.`
                : ''}
            </p>
          </div>
          <Button
            type="button"
            variant={state.limitEntryWindow ? 'default' : 'outline'}
            size="sm"
            onClick={() => onChange({ limitEntryWindow: !state.limitEntryWindow })}
          >
            {state.limitEntryWindow ? 'Limited' : 'All day'}
          </Button>
        </div>
        {state.limitEntryWindow && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="entry-window-start">Start time</Label>
              <Input
                id="entry-window-start"
                type="time"
                step={60}
                value={state.entryWindowStart}
                onChange={(event) => onChange({ entryWindowStart: event.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="entry-window-end">End time</Label>
              <Input
                id="entry-window-end"
                type="time"
                step={60}
                value={state.entryWindowEnd}
                onChange={(event) => onChange({ entryWindowEnd: event.target.value })}
              />
            </div>
          </div>
        )}
      </div>

      <div className="space-y-3 rounded-md border border-border p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-sm font-medium">Session exit</p>
            <p className="text-xs text-muted-foreground">
              Close any open position at this exchange-local time when stop-loss and
              take-profit did not fire. Uses the dataset timezone (e.g. 14:55 IST).
            </p>
          </div>
          <Button
            type="button"
            variant={state.enableSessionExit ? 'default' : 'outline'}
            size="sm"
            onClick={() => onChange({ enableSessionExit: !state.enableSessionExit })}
          >
            {state.enableSessionExit ? 'Enabled' : 'Disabled'}
          </Button>
        </div>
        {state.enableSessionExit && (
          <div className="space-y-2 sm:max-w-xs">
            <Label htmlFor="session-exit-at">Exit time</Label>
            <Input
              id="session-exit-at"
              type="time"
              step={60}
              value={state.sessionExitAt}
              onChange={(event) => onChange({ sessionExitAt: event.target.value })}
            />
          </div>
        )}
      </div>

      {showStopLossOverride && (
        <div className="space-y-3 rounded-md border border-border p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium">Override stop loss</p>
              <p className="text-xs text-muted-foreground">
                Replace the library strategy&apos;s stop-loss rule for this run. Stops are measured
                from entry price and trigger when the bar&apos;s low (long) or high (short) crosses
                the level. Take-profit and other exits are unchanged.
              </p>
            </div>
            <Button
              type="button"
              variant={state.overrideStopLoss ? 'default' : 'outline'}
              size="sm"
              onClick={() => onChange({ overrideStopLoss: !state.overrideStopLoss })}
            >
              {state.overrideStopLoss ? 'Overridden' : 'Strategy default'}
            </Button>
          </div>
          {state.overrideStopLoss && (
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="stop-loss-mode">Stop type</Label>
                <Select
                  value={state.stopLossOverrideMode}
                  onValueChange={(value) =>
                    onChange({
                      stopLossOverrideMode: value as WorkflowState['stopLossOverrideMode'],
                      stopLossValue:
                        value === 'atr' ? DEFAULT_STOP_LOSS_ATR : DEFAULT_STOP_LOSS_PERCENT,
                    })
                  }
                >
                  <SelectTrigger id="stop-loss-mode">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="percent">Percent of entry price</SelectItem>
                    <SelectItem value="atr">ATR multiple at entry</SelectItem>
                    <SelectItem value="disabled">Disabled (no stop)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {state.stopLossOverrideMode !== 'disabled' && (
                <div className="space-y-2">
                  <Label htmlFor="stop-loss-value">
                    {state.stopLossOverrideMode === 'percent'
                      ? 'Stop distance (%)'
                      : 'Stop distance (× ATR)'}
                  </Label>
                  <Input
                    id="stop-loss-value"
                    type="number"
                    min="0.1"
                    step="0.1"
                    max={state.stopLossOverrideMode === 'percent' ? 25 : 10}
                    value={state.stopLossValue}
                    onChange={(event) => onChange({ stopLossValue: event.target.value })}
                  />
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {hasAnomalies && (
        <div className="space-y-3 rounded-md border border-border p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium">Skip trading on anomaly days</p>
              <p className="text-xs text-muted-foreground">
                Bars still replay and indicators keep updating. New entries are blocked on the
                selected days; exits on open positions are still allowed. Does not remove data from
                the dataset.
              </p>
            </div>
            <Button
              type="button"
              variant={state.skipTradesOnPriceAnomalyDays ? 'default' : 'outline'}
              size="sm"
              onClick={() =>
                onChange({ skipTradesOnPriceAnomalyDays: !state.skipTradesOnPriceAnomalyDays })
              }
            >
              {state.skipTradesOnPriceAnomalyDays ? 'Enabled' : 'Disabled'}
            </Button>
          </div>
          {state.skipTradesOnPriceAnomalyDays && (
            <ul className="space-y-2 text-sm">
              {anomalyRows.map((row) => {
                const keyMap = {
                  intraday_spikes_over_10: 'skipTradesOnIntradayAnomalies10pct',
                  intraday_spikes_over_20: 'skipTradesOnIntradayAnomalies20pct',
                  cross_day_spikes_over_10: 'skipTradesOnCrossDayAnomalies10pct',
                  cross_day_spikes_over_20: 'skipTradesOnCrossDayAnomalies20pct',
                } as const
                const optionKey = keyMap[row.key as keyof typeof keyMap]
                if (!optionKey) return null
                return (
                  <li
                    key={row.key}
                    className="flex items-start gap-3 rounded-md border border-border/60 bg-background px-3 py-2"
                  >
                    <input
                      id={`skip-${row.key}`}
                      type="checkbox"
                      className="mt-1"
                      checked={state[optionKey]}
                      onChange={(event) =>
                        onChange({ [optionKey]: event.target.checked } as Partial<WorkflowState>)
                      }
                    />
                    <label htmlFor={`skip-${row.key}`} className="min-w-0 flex-1">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium">{row.label}</span>
                        <span className="tabular text-muted-foreground">
                          {row.dayCount} day{row.dayCount === 1 ? '' : 's'}
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
          )}
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="explain-level">Explainability</Label>
        <Select
          value={explainLevel}
          onValueChange={(value) =>
            onChange({ explainLevel: value as ExplainLevel, explainLevelChosen: true })
          }
        >
          <SelectTrigger id="explain-level" className="w-full sm:w-72">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {EXPLAIN_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label} — {option.hint}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {isRecommendedLevel && supportsConditionTracing && (
          <p className="text-xs text-muted-foreground">
            Set from this strategy&apos;s recommendation, because it traces every condition it
            evaluates.
          </p>
        )}
      </div>

      {warning && (
        <div className="flex gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-300">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <p>{warning}</p>
        </div>
      )}
    </div>
  )
}
