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

import { explainabilityWarning, type ExplainLevel, type WorkflowState } from '../workflow'

interface ExecutionSettingsProps {
  state: WorkflowState
  /** The level the run will use, after the strategy's recommendation is applied. */
  explainLevel: ExplainLevel
  /** Whether the selected strategy traces conditions, for the downgrade warning. */
  supportsConditionTracing: boolean | undefined
  isRecommendedLevel: boolean
  /** Total bars in the selected dataset, when known. */
  datasetBarCount?: number
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
  onChange,
}: ExecutionSettingsProps) {
  const warning = explainabilityWarning(explainLevel, supportsConditionTracing)

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
