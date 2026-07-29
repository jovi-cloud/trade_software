import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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

import { useUpdateBacktestRunResearch } from '../queries'
import type { BacktestRun, BacktestRunResearchInput } from '../types'

interface ResearchJournalProps {
  run: BacktestRun
}

const RATING_OPTIONS = ['1', '2', '3', '4', '5'] as const

const TIMELINE_STEPS = [
  { key: 'run_created', label: 'Run created' },
  { key: 'research_completed', label: 'Research completed' },
  { key: 'conclusion_written', label: 'Conclusion written' },
] as const

function toFormState(run: BacktestRun): BacktestRunResearchInput {
  return {
    experiment_name: run.experiment_name ?? '',
    hypothesis: run.hypothesis ?? '',
    what_changed: run.what_changed ?? '',
    expected_result: run.expected_result ?? '',
    actual_result: run.actual_result ?? '',
    conclusion: run.conclusion ?? '',
    next_experiment: run.next_experiment ?? '',
    tags: run.tags ?? '',
    rating: run.rating ?? null,
    notes: run.notes ?? '',
  }
}

export function ResearchJournal({ run }: ResearchJournalProps) {
  const [form, setForm] = useState(() => toFormState(run))
  const updateResearch = useUpdateBacktestRunResearch(run.id)

  const completion = updateResearch.isSuccess && updateResearch.data
    ? updateResearch.data.research_completion_pct
    : run.research_completion_pct
  const timeline = updateResearch.isSuccess && updateResearch.data
    ? updateResearch.data.research_timeline
    : run.research_timeline

  return (
    <Card>
      <CardHeader className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <CardTitle className="text-base">Research Journal</CardTitle>
          <div className="text-right">
            <p className="text-xs text-muted-foreground">Research complete</p>
            <p className="text-2xl font-semibold">{completion}%</p>
          </div>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-all"
            style={{ width: `${completion}%` }}
          />
        </div>
        <ol className="space-y-3 text-sm">
          {TIMELINE_STEPS.map((step) => {
            const done = timeline[step.key]
            return (
              <li key={step.key} className="flex items-center gap-3">
                <span
                  className={`flex size-5 shrink-0 items-center justify-center rounded-full text-xs ${
                    done
                      ? 'bg-primary text-primary-foreground'
                      : 'border border-border text-muted-foreground'
                  }`}
                >
                  {done ? '✓' : '·'}
                </span>
                <p className={done ? 'font-medium' : 'text-muted-foreground'}>{step.label}</p>
              </li>
            )
          })}
        </ol>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <Field
            id="experiment-name"
            label="Experiment Name"
            value={form.experiment_name ?? ''}
            onChange={(value) => setForm((current) => ({ ...current, experiment_name: value }))}
          />
          <div className="space-y-2">
            <Label htmlFor="rating">Rating</Label>
            <Select
              value={form.rating ? String(form.rating) : 'none'}
              onValueChange={(value) =>
                setForm((current) => ({
                  ...current,
                  rating: value === 'none' ? null : Number(value),
                }))
              }
            >
              <SelectTrigger id="rating">
                <SelectValue placeholder="Rate this experiment" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">No rating</SelectItem>
                {RATING_OPTIONS.map((value) => (
                  <SelectItem key={value} value={value}>
                    {value} / 5
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <TextField
          id="hypothesis"
          label="Hypothesis"
          value={form.hypothesis ?? ''}
          onChange={(value) => setForm((current) => ({ ...current, hypothesis: value }))}
          placeholder="Why do you think this should work?"
        />
        <TextField
          id="what-changed"
          label="What Changed"
          value={form.what_changed ?? ''}
          onChange={(value) => setForm((current) => ({ ...current, what_changed: value }))}
          placeholder="What is different from the previous version or run?"
        />
        <TextField
          id="expected-result"
          label="Expected Result"
          value={form.expected_result ?? ''}
          onChange={(value) => setForm((current) => ({ ...current, expected_result: value }))}
          placeholder="What outcome were you looking for?"
        />
        <TextField
          id="actual-result"
          label="Actual Result"
          value={form.actual_result ?? ''}
          onChange={(value) => setForm((current) => ({ ...current, actual_result: value }))}
          placeholder="What actually happened in this run?"
        />
        <TextField
          id="conclusion"
          label="Conclusion"
          value={form.conclusion ?? ''}
          onChange={(value) => setForm((current) => ({ ...current, conclusion: value }))}
          placeholder="Did it work? What did you learn?"
        />
        <TextField
          id="next-experiment"
          label="Next Experiment"
          value={form.next_experiment ?? ''}
          onChange={(value) => setForm((current) => ({ ...current, next_experiment: value }))}
          placeholder="What should be tried next?"
        />
        <Field
          id="tags"
          label="Tags"
          value={form.tags ?? ''}
          onChange={(value) => setForm((current) => ({ ...current, tags: value }))}
          placeholder="mean-reversion, intraday, nifty"
        />

        <div className="flex justify-end">
          <Button
            type="button"
            disabled={updateResearch.isPending}
            onClick={() =>
              updateResearch.mutate(form, {
                onSuccess: (saved) => setForm(toFormState(saved)),
              })
            }
          >
            {updateResearch.isPending ? 'Saving…' : 'Save Research'}
          </Button>
        </div>

        {updateResearch.isError && (
          <p className="text-sm text-destructive">Unable to save research. Please try again.</p>
        )}
      </CardContent>
    </Card>
  )
}

interface FieldProps {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

function Field({ id, label, value, onChange, placeholder }: FieldProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
    </div>
  )
}

interface TextFieldProps extends FieldProps {
  rows?: number
}

function TextField({ id, label, value, onChange, placeholder, rows = 3 }: TextFieldProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor={id}>{label}</Label>
      <Textarea
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        rows={rows}
      />
    </div>
  )
}
