import { formatCurrency, formatDate, formatDuration, formatInteger } from '@/lib/format'

import type { ComparisonReport } from '../types'

interface ExecutionComparisonPanelProps {
  report: ComparisonReport
}

export function ExecutionComparisonPanel({ report }: ExecutionComparisonPanelProps) {
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-sm">
        <thead className="bg-muted/40 text-xs text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-medium">Run</th>
            <th className="px-3 py-2 font-medium">Experiment</th>
            <th className="px-3 py-2 font-medium">Engine</th>
            <th className="px-3 py-2 font-medium">Executed</th>
            <th className="px-3 py-2 font-medium">Duration</th>
            <th className="px-3 py-2 font-medium">Bars</th>
            <th className="px-3 py-2 font-medium">Trades</th>
            <th className="px-3 py-2 font-medium">Capital</th>
          </tr>
        </thead>
        <tbody>
          {report.execution_rows.map((row) => (
            <tr key={row.run_id} className="border-t border-border">
              <td className="px-3 py-2">Run {row.run_label}</td>
              <td className="px-3 py-2">{row.experiment_name ?? '—'}</td>
              <td className="px-3 py-2">{row.engine_version}</td>
              <td className="px-3 py-2">{formatDate(row.execution_completed_at)}</td>
              <td className="px-3 py-2">{formatDuration(row.execution_time_ms)}</td>
              <td className="px-3 py-2">{formatInteger(row.bars_processed)}</td>
              <td className="px-3 py-2">{formatInteger(row.trade_count)}</td>
              <td className="px-3 py-2">{formatCurrency(row.initial_capital)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
