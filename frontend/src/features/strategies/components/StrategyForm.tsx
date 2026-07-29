import { useState, type FormEvent } from 'react'

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
import { Textarea } from '@/components/ui/textarea'

import { MARKET_TYPES, PRIORITIES, STRATEGY_STATUSES, TIMEFRAMES } from '../types'
import type { MarketType, Priority, StrategyCreateInput, StrategyStatus, Timeframe } from '../types'

export interface StrategyFormValues {
  name: string
  description: string
  hypothesis: string
  market_type: MarketType
  instrument: string
  timeframe: Timeframe | undefined
  status: StrategyStatus
  priority: Priority
  confidence_level: number
  tags: string
}

const EMPTY_VALUES: StrategyFormValues = {
  name: '',
  description: '',
  hypothesis: '',
  market_type: 'equity',
  instrument: '',
  timeframe: undefined,
  status: 'draft',
  priority: 'medium',
  confidence_level: 5,
  tags: '',
}

function titleCase(value: string): string {
  return `${value[0]?.toUpperCase()}${value.slice(1)}`
}

interface StrategyFormProps {
  initialValues?: Partial<StrategyFormValues>
  submitLabel: string
  onSubmit: (input: StrategyCreateInput) => Promise<void>
  isSubmitting: boolean
  onCancel?: () => void
}

export function StrategyForm({
  initialValues,
  submitLabel,
  onSubmit,
  isSubmitting,
  onCancel,
}: StrategyFormProps) {
  const [values, setValues] = useState<StrategyFormValues>({ ...EMPTY_VALUES, ...initialValues })
  const [fieldError, setFieldError] = useState<string | null>(null)

  function update<K extends keyof StrategyFormValues>(key: K, value: StrategyFormValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }))
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!values.name.trim()) return setFieldError('Name is required.')
    if (!values.description.trim()) return setFieldError('Description is required.')
    if (!values.instrument.trim()) return setFieldError('Instrument is required.')
    if (!values.timeframe) return setFieldError('Timeframe is required.')
    setFieldError(null)

    await onSubmit({
      name: values.name.trim(),
      description: values.description.trim(),
      hypothesis: values.hypothesis.trim() || null,
      market_type: values.market_type,
      instrument: values.instrument.trim(),
      timeframe: values.timeframe,
      status: values.status,
      priority: values.priority,
      confidence_level: values.confidence_level,
      tags: values.tags.trim() || null,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl space-y-5">
      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <Input
          id="name"
          value={values.name}
          onChange={(e) => update('name', e.target.value)}
          placeholder="Opening Range Breakout"
          maxLength={200}
          required
        />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="space-y-2">
          <Label htmlFor="market_type">Market Type</Label>
          <Select
            value={values.market_type}
            onValueChange={(value) => update('market_type', value as MarketType)}
          >
            <SelectTrigger id="market_type" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MARKET_TYPES.map((type) => (
                <SelectItem key={type} value={type}>
                  {type === 'fx' ? 'FX' : titleCase(type)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="instrument">Instrument</Label>
          <Input
            id="instrument"
            value={values.instrument}
            onChange={(e) => update('instrument', e.target.value)}
            placeholder="NIFTY"
            maxLength={100}
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="timeframe">Timeframe</Label>
          <Select
            value={values.timeframe}
            onValueChange={(value) => update('timeframe', value as Timeframe)}
          >
            <SelectTrigger id="timeframe" className="w-full">
              <SelectValue placeholder="Select a timeframe" />
            </SelectTrigger>
            <SelectContent>
              {TIMEFRAMES.map((tf) => (
                <SelectItem key={tf} value={tf}>
                  {tf}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">Description</Label>
        <Textarea
          id="description"
          value={values.description}
          onChange={(e) => update('description', e.target.value)}
          placeholder="A short summary shown on the strategy card."
          maxLength={2000}
          rows={3}
          required
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="hypothesis">Hypothesis</Label>
        <Textarea
          id="hypothesis"
          value={values.hypothesis}
          onChange={(e) => update('hypothesis', e.target.value)}
          placeholder="Why do you think this works? The research anchor for this idea."
          maxLength={8000}
          rows={4}
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="status">Status</Label>
          <Select
            value={values.status}
            onValueChange={(value) => update('status', value as StrategyStatus)}
          >
            <SelectTrigger id="status" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {STRATEGY_STATUSES.map((status) => (
                <SelectItem key={status} value={status}>
                  {titleCase(status)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="tags">Tags</Label>
          <Input
            id="tags"
            value={values.tags}
            onChange={(e) => update('tags', e.target.value)}
            placeholder="intraday, breakout"
            maxLength={500}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <Label htmlFor="priority">Priority</Label>
          <Select
            value={values.priority}
            onValueChange={(value) => update('priority', value as Priority)}
          >
            <SelectTrigger id="priority" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PRIORITIES.map((priority) => (
                <SelectItem key={priority} value={priority}>
                  {titleCase(priority)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="confidence_level">Confidence (1–10)</Label>
          <Input
            id="confidence_level"
            type="number"
            min={1}
            max={10}
            value={values.confidence_level}
            onChange={(e) => update('confidence_level', Number(e.target.value))}
          />
        </div>
      </div>

      {fieldError && <p className="text-sm text-destructive">{fieldError}</p>}

      <div className="flex items-center gap-2 pt-2">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Saving…' : submitLabel}
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel} disabled={isSubmitting}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}
