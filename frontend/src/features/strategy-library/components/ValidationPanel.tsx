import type { ParamValidation } from '../types'

interface ValidationPanelProps {
  validation: ParamValidation | undefined
  isValidating: boolean
}

export function ValidationPanel({ validation, isValidating }: ValidationPanelProps) {
  // Both lists are omitted from the payload when empty, which is the common case.
  const errors = validation?.errors ?? []
  const warnings = validation?.warnings ?? []

  return (
    <section className="rounded-lg border border-border bg-muted/30 p-4">
      <h3 className="mb-3 text-sm font-semibold">Validation</h3>
      {isValidating && <p className="text-sm text-muted-foreground">Checking parameters…</p>}
      {!isValidating && !validation && (
        <p className="text-sm text-muted-foreground">
          Edit parameters to validate them before running a backtest.
        </p>
      )}
      {!isValidating && validation && (
        <div className="space-y-3">
          <p
            className={
              validation.is_valid
                ? 'text-sm font-medium text-emerald-700 dark:text-emerald-400'
                : 'text-sm font-medium text-destructive'
            }
          >
            {validation.is_valid
              ? 'Parameters are valid and ready to run.'
              : 'Fix the errors below before running.'}
          </p>
          {errors.length > 0 && (
            <ul className="space-y-1 text-sm text-destructive">
              {errors.map((finding) => (
                <li key={`${finding.code}-${finding.param ?? 'global'}-${finding.message}`}>
                  {finding.param ? `${finding.param}: ` : ''}
                  {finding.message}
                </li>
              ))}
            </ul>
          )}
          {warnings.length > 0 && (
            <ul className="space-y-1 text-sm text-amber-700 dark:text-amber-400">
              {warnings.map((finding) => (
                <li key={`${finding.code}-${finding.param ?? 'global'}-${finding.message}`}>
                  {finding.param ? `${finding.param}: ` : ''}
                  {finding.message}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}
