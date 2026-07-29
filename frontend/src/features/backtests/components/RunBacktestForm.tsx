import { useMemo, useState, type FormEvent } from 'react'

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
import { Skeleton } from '@/components/ui/skeleton'
import { useDatasets } from '@/features/datasets/queries'
import { useStrategies } from '@/features/strategies/queries'

import type { BacktestExecuteInput } from '../types'

interface RunBacktestFormProps {
  onSubmit: (input: BacktestExecuteInput) => Promise<void>
  isSubmitting: boolean
}

const DEFAULT_CAPITAL = 100_000
const DEFAULT_COMMISSION = 0
const DEFAULT_SLIPPAGE = 0

export function RunBacktestForm({ onSubmit, isSubmitting }: RunBacktestFormProps) {
  const strategies = useStrategies({ limit: 100, sort: 'name', order: 'asc' })
  const datasets = useDatasets({ limit: 100, sort: 'name', order: 'asc' })

  const [strategyId, setStrategyId] = useState('')
  const [datasetId, setDatasetId] = useState('')
  const [initialCapital, setInitialCapital] = useState(String(DEFAULT_CAPITAL))
  const [commission, setCommission] = useState(String(DEFAULT_COMMISSION))
  const [slippage, setSlippage] = useState(String(DEFAULT_SLIPPAGE))
  const [fieldError, setFieldError] = useState<string | null>(null)

  const readyDatasets = useMemo(
    () => (datasets.data?.items ?? []).filter((dataset) => dataset.import_status === 'completed'),
    [datasets.data?.items],
  )

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!strategyId) return setFieldError('Choose a strategy.')
    if (!datasetId) return setFieldError('Choose a dataset.')

    const capital = Number(initialCapital)
    const commissionValue = Number(commission)
    const slippageValue = Number(slippage)

    if (!Number.isFinite(capital) || capital <= 0) {
      return setFieldError('Initial capital must be a positive number.')
    }
    if (!Number.isFinite(commissionValue) || commissionValue < 0) {
      return setFieldError('Commission must be zero or greater.')
    }
    if (!Number.isFinite(slippageValue) || slippageValue < 0) {
      return setFieldError('Slippage must be zero or greater.')
    }

    setFieldError(null)
    await onSubmit({
      strategy_id: strategyId,
      dataset_id: datasetId,
      initial_capital: capital,
      commission: commissionValue,
      slippage: slippageValue,
    })
  }

  if (strategies.isLoading || datasets.isLoading) {
    return (
      <div className="max-w-2xl space-y-4">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  if (strategies.isError || datasets.isError) {
    return (
      <p className="text-sm text-destructive">
        Unable to load strategies or datasets. Check that the backend is running.
      </p>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl space-y-5">
      <div className="space-y-2">
        <Label htmlFor="strategy">Strategy</Label>
        <Select value={strategyId} onValueChange={setStrategyId}>
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

      <div className="space-y-2">
        <Label htmlFor="dataset">Dataset</Label>
        <Select value={datasetId} onValueChange={setDatasetId}>
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

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-2">
          <Label htmlFor="capital">Initial capital</Label>
          <Input
            id="capital"
            type="number"
            min="0"
            step="any"
            value={initialCapital}
            onChange={(event) => setInitialCapital(event.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="commission">Commission</Label>
          <Input
            id="commission"
            type="number"
            min="0"
            step="any"
            value={commission}
            onChange={(event) => setCommission(event.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="slippage">Slippage</Label>
          <Input
            id="slippage"
            type="number"
            min="0"
            step="any"
            value={slippage}
            onChange={(event) => setSlippage(event.target.value)}
          />
        </div>
      </div>

      {fieldError && <p className="text-sm text-destructive">{fieldError}</p>}

      <Button type="submit" disabled={isSubmitting || readyDatasets.length === 0}>
        {isSubmitting ? 'Running…' : 'Run backtest'}
      </Button>
    </form>
  )
}
