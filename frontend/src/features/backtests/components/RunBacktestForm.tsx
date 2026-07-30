import { useCallback, useMemo, useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { useDatasetVersions, useDatasets } from '@/features/datasets/queries'
import { useStrategies } from '@/features/strategies/queries'
import { useLibraryStrategies } from '@/features/strategy-library/queries'
import type {
  LibraryStrategy,
  ParamValidation,
  ParamValue,
} from '@/features/strategy-library/types'
import { cn } from '@/lib/utils'

import {
  missingRequirements,
  parseNumericSettings,
  resolveExplainLevel,
  selectLibraryStrategy,
  toExecuteInput,
  type ExecuteInput,
  type StrategySource,
  type WorkflowState,
} from '../workflow'
import { updateWorkflow } from '../workflowStore'
import { DatasetVersionSelector } from './DatasetVersionSelector'
import { ExecutionSettings } from './ExecutionSettings'
import { LibraryStrategyConfig } from './LibraryStrategyConfig'

interface RunBacktestFormProps {
  state: WorkflowState
  onSubmit: (input: ExecuteInput) => Promise<void>
  isSubmitting: boolean
}

const LIST_LIMIT = 200

export function RunBacktestForm({ state, onSubmit, isSubmitting }: RunBacktestFormProps) {
  const library = useLibraryStrategies({ limit: LIST_LIMIT, valid_only: true })
  const strategies = useStrategies({ limit: 100, sort: 'name', order: 'asc' })
  const datasets = useDatasets({ limit: 100, sort: 'name', order: 'asc' })
  const { data: datasetVersions = [] } = useDatasetVersions(state.datasetId)

  const [selected, setSelected] = useState<LibraryStrategy | null>(null)
  const [validation, setValidation] = useState<ParamValidation | undefined>(undefined)
  const [fieldError, setFieldError] = useState<string | null>(null)

  const readyDatasets = useMemo(
    () =>
      (datasets.data?.items ?? []).filter(
        (dataset) =>
          (dataset.lifecycle === undefined || dataset.lifecycle === 'active') &&
          (dataset.status === 'valid' || dataset.import_status === 'completed'),
      ),
    [datasets.data?.items],
  )

  const selectedDataset = readyDatasets.find((dataset) => dataset.id === state.datasetId)

  // The strategy detail arrives asynchronously; until it does there is no
  // recommendation to apply and the stored level stands.
  const isCurrentStrategy = selected?.id === state.libraryStrategyId
  const recommended =
    state.source === 'library' && isCurrentStrategy
      ? selected?.recommended_explain_level
      : undefined
  const explainLevel = resolveExplainLevel(state, recommended)
  const supportsTracing =
    state.source === 'library' && isCurrentStrategy ? selected?.supports_condition_tracing : false

  const patch = useCallback((changes: Partial<WorkflowState>) => updateWorkflow(changes), [])

  const handleStrategyLoaded = useCallback((strategy: LibraryStrategy) => {
    setSelected(strategy)
    // Open the editor on the declared defaults the first time a strategy is
    // picked; a returning trader keeps whatever they had edited.
    updateWorkflow((current) =>
      current.libraryStrategyId === strategy.id && Object.keys(current.params).length === 0
        ? { ...current, params: strategy.default_params as Record<string, ParamValue> }
        : current,
    )
  }, [])

  function chooseSource(source: StrategySource) {
    setFieldError(null)
    patch({ source })
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const missing = missingRequirements(state)
    if (missing.length > 0) {
      return setFieldError(`Choose ${missing.join(' and ')}.`)
    }
    if (state.source === 'library' && validation && !validation.is_valid) {
      return setFieldError('Fix the parameter errors before running.')
    }

    const settings = parseNumericSettings(state)
    if (!settings.ok) return setFieldError(settings.error)

    setFieldError(null)
    await onSubmit(toExecuteInput(state, settings.values, explainLevel))
  }

  if (strategies.isLoading || datasets.isLoading || library.isLoading) {
    return (
      <div className="max-w-4xl space-y-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  if (strategies.isError || datasets.isError || library.isError) {
    return (
      <p className="text-sm text-destructive">
        Unable to load strategies or datasets. Check that the backend is running.
      </p>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-4xl space-y-6">
      <div className="space-y-2">
        <Label>Strategy source</Label>
        <div className="flex gap-2" role="radiogroup" aria-label="Strategy source">
          <SourceButton
            label="Library strategy"
            hint="Built in, configurable, documented"
            isActive={state.source === 'library'}
            onClick={() => chooseSource('library')}
          />
          <SourceButton
            label="My strategy"
            hint="Code you have written and saved"
            isActive={state.source === 'user'}
            onClick={() => chooseSource('user')}
          />
        </div>
      </div>

      {state.source === 'library' ? (
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="library-strategy">Library strategy</Label>
            <Select
              value={state.libraryStrategyId}
              onValueChange={(value) =>
                updateWorkflow((current) => selectLibraryStrategy(current, value))
              }
            >
              <SelectTrigger id="library-strategy">
                <SelectValue placeholder="Select a library strategy" />
              </SelectTrigger>
              <SelectContent>
                {(library.data?.items ?? []).map((item) => (
                  <SelectItem key={item.id} value={item.id}>
                    {item.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {state.libraryStrategyId && (
            <LibraryStrategyConfig
              strategyId={state.libraryStrategyId}
              params={state.params}
              onParamsChange={(params) => patch({ params })}
              onStrategyLoaded={handleStrategyLoaded}
              onValidationChange={setValidation}
            />
          )}
        </div>
      ) : (
        <div className="space-y-2">
          <Label htmlFor="strategy">Strategy</Label>
          <Select
            value={state.userStrategyId}
            onValueChange={(value) => patch({ userStrategyId: value })}
          >
            <SelectTrigger id="strategy">
              <SelectValue placeholder="Select a strategy" />
            </SelectTrigger>
            <SelectContent>
              {(strategies.data?.items ?? []).map((strategy) => (
                <SelectItem key={strategy.id} value={strategy.id}>
                  {strategy.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="dataset">Dataset</Label>
        <Select
          value={state.datasetId}
          onValueChange={(value) => patch({ datasetId: value, datasetVersionNumber: null })}
        >
          <SelectTrigger id="dataset">
            <SelectValue placeholder="Select a dataset" />
          </SelectTrigger>
          <SelectContent>
            {readyDatasets.map((dataset) => (
              <SelectItem key={dataset.id} value={dataset.id}>
                {dataset.name} ({dataset.symbol}, {dataset.timeframe})
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {readyDatasets.length === 0 && (
          <p className="text-xs text-muted-foreground">
            No completed datasets yet. Import one from the Data page first.
          </p>
        )}
      </div>

      {state.datasetId && (
        <DatasetVersionSelector
          datasetId={state.datasetId}
          currentVersionNumber={selectedDataset?.current_version_number}
          versions={datasetVersions}
          selectedVersionNumber={state.datasetVersionNumber}
          onChange={(datasetVersionNumber) => patch({ datasetVersionNumber })}
        />
      )}

      <ExecutionSettings
        state={state}
        explainLevel={explainLevel}
        supportsConditionTracing={supportsTracing}
        isRecommendedLevel={!state.explainLevelChosen}
        onChange={patch}
      />

      {fieldError && <p className="text-sm text-destructive">{fieldError}</p>}

      <Button type="submit" disabled={isSubmitting || readyDatasets.length === 0}>
        {isSubmitting ? 'Running…' : 'Run backtest'}
      </Button>
    </form>
  )
}

interface SourceButtonProps {
  label: string
  hint: string
  isActive: boolean
  onClick: () => void
}

function SourceButton({ label, hint, isActive, onClick }: SourceButtonProps) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={isActive}
      onClick={onClick}
      className={cn(
        'flex-1 rounded-md border px-4 py-3 text-left transition-colors',
        isActive
          ? 'border-primary bg-primary/5'
          : 'border-border hover:border-muted-foreground/40 hover:bg-muted/40',
      )}
    >
      <span className="block text-sm font-medium">{label}</span>
      <span className="block text-xs text-muted-foreground">{hint}</span>
    </button>
  )
}
