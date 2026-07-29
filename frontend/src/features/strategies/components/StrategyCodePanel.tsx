import { useState } from 'react'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ErrorState } from '@/components/common/ErrorState'
import { Skeleton } from '@/components/ui/skeleton'
import { getErrorMessage } from '@/lib/apiClient'
import { formatDate } from '@/lib/format'

import { StrategyCodeEditor } from './StrategyCodeEditor'
import { StrategyCodeValidationResults } from './StrategyCodeValidationResults'
import { useSaveStrategyCode, useStrategyCode, useValidateStrategyCode } from '../queries'
import { DEFAULT_STRATEGY_TEMPLATE } from '../types'
import type { StrategyCode, StrategyValidationResult } from '../types'

function resultFromSavedCode(code: StrategyCode): StrategyValidationResult {
  return {
    valid: code.compiled_successfully,
    error: code.compile_error ? { line: null, column: null, message: code.compile_error } : null,
  }
}

interface StrategyCodePanelProps {
  strategyId: string
}

export function StrategyCodePanel({ strategyId }: StrategyCodePanelProps) {
  const { data: code, isLoading, isError, error, refetch } = useStrategyCode(strategyId)

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-1/3" />
        <Skeleton className="h-[520px]" />
      </div>
    )
  }

  if (isError || !code) {
    return (
      <ErrorState
        message={getErrorMessage(error, "Unable to load this strategy's code.")}
        onRetry={() => refetch()}
      />
    )
  }

  return <StrategyCodeEditorPanel strategyId={strategyId} code={code} />
}

function StrategyCodeEditorPanel({ strategyId, code }: { strategyId: string; code: StrategyCode }) {
  const [draft, setDraft] = useState(code.code)
  const [savedCode, setSavedCode] = useState(code.code)
  const [result, setResult] = useState<StrategyValidationResult>(() => resultFromSavedCode(code))
  const [confirmingReset, setConfirmingReset] = useState(false)

  const saveMutation = useSaveStrategyCode(strategyId)
  const validateMutation = useValidateStrategyCode(strategyId)

  const isDirty = draft !== savedCode

  async function handleSave() {
    const saved = await saveMutation.mutateAsync({ code: draft })
    setSavedCode(saved.code)
    setResult(resultFromSavedCode(saved))
  }

  async function handleValidate() {
    const validation = await validateMutation.mutateAsync({ code: draft })
    setResult(validation)
  }

  function handleReset() {
    setDraft(DEFAULT_STRATEGY_TEMPLATE)
    setResult({ valid: true, error: null })
    setConfirmingReset(false)
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Python Strategy Editor</span>
            <span className="text-xs font-normal text-muted-foreground">
              {isDirty ? 'Unsaved changes' : `Saved ${formatDate(code.updated_at)}`}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <StrategyCodeEditor value={draft} onChange={setDraft} />

          <div className="flex items-center gap-2">
            <Button onClick={handleSave} disabled={saveMutation.isPending || !isDirty}>
              {saveMutation.isPending ? 'Saving…' : 'Save Code'}
            </Button>
            <Button
              variant="outline"
              onClick={handleValidate}
              disabled={validateMutation.isPending}
            >
              {validateMutation.isPending ? 'Validating…' : 'Validate'}
            </Button>
            <Button variant="outline" onClick={() => setConfirmingReset(true)}>
              Reset to Template
            </Button>
            {saveMutation.isError && (
              <p className="text-sm text-destructive">
                {getErrorMessage(saveMutation.error, 'Unable to save code.')}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      <StrategyCodeValidationResults result={result} isValidating={validateMutation.isPending} />

      <AlertDialog open={confirmingReset} onOpenChange={setConfirmingReset}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Reset to template?</AlertDialogTitle>
            <AlertDialogDescription>
              This replaces the code in the editor with the default strategy template. Your current
              edits are not saved until you click Save Code, and resetting discards them from the
              editor.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleReset}>Reset</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
