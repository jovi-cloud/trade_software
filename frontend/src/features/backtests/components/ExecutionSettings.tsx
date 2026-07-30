import { AlertTriangle } from 'lucide-react'

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
