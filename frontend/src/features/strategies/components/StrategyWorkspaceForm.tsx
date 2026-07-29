import { useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

import type { Strategy, StrategyUpdateInput } from '../types'

interface WorkspaceValues {
  hypothesis: string
  entry_rules: string
  exit_rules: string
  stop_loss_method: string
  target_method: string
  position_sizing: string
  assumptions: string
  known_weaknesses: string
  ideas_for_improvement: string
}

function valuesFrom(strategy: Strategy): WorkspaceValues {
  return {
    hypothesis: strategy.hypothesis ?? '',
    entry_rules: strategy.entry_rules ?? '',
    exit_rules: strategy.exit_rules ?? '',
    stop_loss_method: strategy.stop_loss_method ?? '',
    target_method: strategy.target_method ?? '',
    position_sizing: strategy.position_sizing ?? '',
    assumptions: strategy.assumptions ?? '',
    known_weaknesses: strategy.known_weaknesses ?? '',
    ideas_for_improvement: strategy.ideas_for_improvement ?? '',
  }
}

interface StrategyWorkspaceFormProps {
  strategy: Strategy
  onSave: (input: StrategyUpdateInput) => Promise<void>
  isSaving: boolean
}

/**
 * The research document itself: hypothesis, trading rules, risk management,
 * research notes. Explicit Save only - no autosave (Phase 1B rule).
 */
export function StrategyWorkspaceForm({ strategy, onSave, isSaving }: StrategyWorkspaceFormProps) {
  const [values, setValues] = useState<WorkspaceValues>(() => valuesFrom(strategy))
  const [saveError, setSaveError] = useState<string | null>(null)
  const [savedAt, setSavedAt] = useState<number | null>(null)

  function update<K extends keyof WorkspaceValues>(key: K, value: WorkspaceValues[K]) {
    setValues((prev) => ({ ...prev, [key]: value }))
    setSavedAt(null)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSaveError(null)
    try {
      await onSave({
        hypothesis: values.hypothesis.trim() || null,
        entry_rules: values.entry_rules.trim() || null,
        exit_rules: values.exit_rules.trim() || null,
        stop_loss_method: values.stop_loss_method.trim() || null,
        target_method: values.target_method.trim() || null,
        position_sizing: values.position_sizing.trim() || null,
        assumptions: values.assumptions.trim() || null,
        known_weaknesses: values.known_weaknesses.trim() || null,
        ideas_for_improvement: values.ideas_for_improvement.trim() || null,
      })
      setSavedAt(Date.now())
    } catch {
      setSaveError('Unable to save changes.')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Hypothesis</CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea
            value={values.hypothesis}
            onChange={(e) => update('hypothesis', e.target.value)}
            placeholder="Why do you think this works? Markdown supported."
            rows={12}
            maxLength={8000}
            className="font-mono text-sm"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Trading Rules</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="entry_rules">Entry Rules</Label>
            <Textarea
              id="entry_rules"
              value={values.entry_rules}
              onChange={(e) => update('entry_rules', e.target.value)}
              placeholder="Exactly when does this strategy enter a trade?"
              rows={6}
              maxLength={8000}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="exit_rules">Exit Rules</Label>
            <Textarea
              id="exit_rules"
              value={values.exit_rules}
              onChange={(e) => update('exit_rules', e.target.value)}
              placeholder="Exactly when does this strategy exit a trade?"
              rows={6}
              maxLength={8000}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Risk Management</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="stop_loss_method">Stop Loss</Label>
            <Textarea
              id="stop_loss_method"
              value={values.stop_loss_method}
              onChange={(e) => update('stop_loss_method', e.target.value)}
              placeholder="How is the stop determined?"
              rows={5}
              maxLength={8000}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="target_method">Target</Label>
            <Textarea
              id="target_method"
              value={values.target_method}
              onChange={(e) => update('target_method', e.target.value)}
              placeholder="How is the target determined?"
              rows={5}
              maxLength={8000}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="position_sizing">Position Sizing</Label>
            <Textarea
              id="position_sizing"
              value={values.position_sizing}
              onChange={(e) => update('position_sizing', e.target.value)}
              placeholder="How much is risked per trade?"
              rows={5}
              maxLength={8000}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Research Notes</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor="assumptions">Assumptions</Label>
            <Textarea
              id="assumptions"
              value={values.assumptions}
              onChange={(e) => update('assumptions', e.target.value)}
              placeholder="What has to be true for this to work?"
              rows={5}
              maxLength={8000}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="known_weaknesses">Known Weaknesses</Label>
            <Textarea
              id="known_weaknesses"
              value={values.known_weaknesses}
              onChange={(e) => update('known_weaknesses', e.target.value)}
              placeholder="Where does this idea break down?"
              rows={5}
              maxLength={8000}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="ideas_for_improvement">Ideas for Improvement</Label>
            <Textarea
              id="ideas_for_improvement"
              value={values.ideas_for_improvement}
              onChange={(e) => update('ideas_for_improvement', e.target.value)}
              placeholder="What would you try next?"
              rows={5}
              maxLength={8000}
            />
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center gap-3">
        <Button type="submit" disabled={isSaving}>
          {isSaving ? 'Saving…' : 'Save Research'}
        </Button>
        {saveError && <p className="text-sm text-destructive">{saveError}</p>}
        {!saveError && savedAt && <p className="text-sm text-muted-foreground">Saved.</p>}
      </div>
    </form>
  )
}
