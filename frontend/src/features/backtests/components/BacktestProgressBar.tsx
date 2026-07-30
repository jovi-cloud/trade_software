import { Button } from '@/components/ui/button'

interface BacktestProgressBarProps {
  progressPct: number
  message: string
  barsProcessed?: number | null
  totalBars?: number | null
  onCancel?: () => void
  isCancelling?: boolean
}

export function BacktestProgressBar({
  progressPct,
  message,
  barsProcessed,
  totalBars,
  onCancel,
  isCancelling = false,
}: BacktestProgressBarProps) {
  const pct = Math.min(100, Math.max(0, Math.round(progressPct)))

  return (
    <div
      className="max-w-4xl rounded-md border border-border bg-muted/30 px-4 py-4"
      role="status"
      aria-live="polite"
      aria-label="Backtest progress"
    >
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-sm">
        <span className="font-medium">{message}</span>
        <div className="flex items-center gap-3">
          <span className="text-muted-foreground">{pct}%</span>
          {onCancel && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onCancel}
              disabled={isCancelling}
            >
              {isCancelling ? 'Cancelling…' : 'Cancel'}
            </Button>
          )}
        </div>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      {totalBars !== null && totalBars !== undefined && totalBars > 0 && (
        <p className="mt-2 text-xs text-muted-foreground">
          {barsProcessed !== null && barsProcessed !== undefined
            ? `${barsProcessed.toLocaleString()} of ${totalBars.toLocaleString()} bars processed`
            : `${totalBars.toLocaleString()} bars to process`}
        </p>
      )}
    </div>
  )
}
