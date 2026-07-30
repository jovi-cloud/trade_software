import { Loader2 } from 'lucide-react'

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
      className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 px-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="backtest-progress-title"
      aria-describedby="backtest-progress-message"
    >
      <div
        className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-2xl"
        role="status"
        aria-live="polite"
        aria-label="Backtest progress"
      >
        <div className="mb-5 flex flex-col items-center text-center">
          <div
            className="mb-4 flex size-12 items-center justify-center rounded-full bg-gradient-to-br from-brand to-brand-secondary text-white shadow-md"
            aria-hidden
          >
            <Loader2 className="size-6 animate-spin" />
          </div>
          <h2 id="backtest-progress-title" className="text-lg font-semibold text-foreground">
            Running backtest
          </h2>
          <p id="backtest-progress-message" className="mt-1 text-sm text-muted-foreground">
            {message}
          </p>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-foreground">Progress</span>
            <span className="tabular-nums text-muted-foreground">{pct}%</span>
          </div>
          <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-gradient-to-r from-brand to-brand-secondary transition-all duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
          {totalBars !== null && totalBars !== undefined && totalBars > 0 && (
            <p className="text-center text-xs text-muted-foreground">
              {barsProcessed !== null && barsProcessed !== undefined
                ? `${barsProcessed.toLocaleString()} of ${totalBars.toLocaleString()} bars processed`
                : `${totalBars.toLocaleString()} bars to process`}
            </p>
          )}
        </div>

        {onCancel && (
          <div className="mt-6 flex justify-center">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onCancel}
              disabled={isCancelling}
            >
              {isCancelling ? 'Cancelling…' : 'Cancel backtest'}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
