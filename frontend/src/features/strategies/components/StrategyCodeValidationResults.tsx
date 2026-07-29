import { CheckCircle2, XCircle } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import type { StrategyValidationResult } from '../types'

interface StrategyCodeValidationResultsProps {
  result: StrategyValidationResult | null
  isValidating: boolean
}

export function StrategyCodeValidationResults({
  result,
  isValidating,
}: StrategyCodeValidationResultsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Validation Results</CardTitle>
      </CardHeader>
      <CardContent>
        {isValidating && <p className="text-sm text-muted-foreground">Checking syntax…</p>}

        {!isValidating && result === null && (
          <p className="text-sm text-muted-foreground">
            Click Validate to check this code&apos;s Python syntax.
          </p>
        )}

        {!isValidating && result !== null && result.valid && (
          <div className="flex items-center gap-2 text-sm font-medium text-profit">
            <CheckCircle2 className="size-4" />
            Syntax Valid
          </div>
        )}

        {!isValidating && result !== null && !result.valid && (
          <div className="flex items-start gap-2 text-sm">
            <XCircle className="mt-0.5 size-4 shrink-0 text-destructive" />
            <div>
              <p className="font-medium text-destructive">Syntax Error</p>
              {result.error && (
                <>
                  {(result.error.line !== null || result.error.column !== null) && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {result.error.line !== null && `Line ${result.error.line}`}
                      {result.error.line !== null && result.error.column !== null && ', '}
                      {result.error.column !== null && `Column ${result.error.column}`}
                    </p>
                  )}
                  <p className="mt-1 font-mono text-sm whitespace-pre-wrap">
                    {result.error.message}
                  </p>
                </>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
