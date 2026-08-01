import type { BacktestRun } from '@/features/backtest-runs/types'
import type { ExecutionResult } from '@/features/backtests/types'

/** Map a persisted run into the shape expected by execution result components. */
export function backtestRunToExecutionResult(run: BacktestRun): ExecutionResult {
  return {
    run_id: run.id,
    completed: run.completed,
    bars_processed: run.bars_processed,
    execution_time_ms: run.execution_time_ms,
    errors: run.errors,
    warnings: run.warnings,
    strategy_logs: run.strategy_logs,
    orders: run.orders,
    trades: run.trades,
    final_cash: run.final_cash,
    position_closed: run.position_closed,
    trade_count: run.trade_count,
    metrics: run.metrics,
    analytics: run.analytics,
    equity_history: run.equity_history,
    candles: run.candles,
    entry_markers: run.entry_markers,
    exit_markers: run.exit_markers,
    trailing_stop_points: run.trailing_stop_points ?? [],
    // The run's lifecycle only. Per-bar and per-trade events are paged in by
    // the Event Explorer rather than inlined on the run.
    explain_events: run.lifecycle_events ?? [],
    explain_level: run.explain_level,
  }
}
