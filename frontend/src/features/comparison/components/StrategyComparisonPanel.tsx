import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

import type { ComparisonReport } from '../types'

interface StrategyComparisonPanelProps {
  report: ComparisonReport
}

export function StrategyComparisonPanel({ report }: StrategyComparisonPanelProps) {
  const [showAllParams, setShowAllParams] = useState(false)
  const diffs = report.strategy_parameter_diffs.filter(
    (item) => showAllParams || item.differs,
  )

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full text-left text-sm">
          <thead className="bg-muted/40 text-xs text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">Run</th>
              <th className="px-3 py-2 font-medium">Strategy</th>
              <th className="px-3 py-2 font-medium">Library</th>
              <th className="px-3 py-2 font-medium">Hash</th>
            </tr>
          </thead>
          <tbody>
            {report.strategy_rows.map((row) => (
              <tr
                key={row.run_id}
                className={`border-t border-border ${row.differs_from_baseline ? 'bg-amber-500/5' : ''}`}
              >
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    Run {row.run_label}
                    {row.differs_from_baseline && (
                      <Badge variant="outline" className="text-xs">
                        Different
                      </Badge>
                    )}
                  </div>
                </td>
                <td className="px-3 py-2">{row.strategy_name}</td>
                <td className="px-3 py-2 font-mono text-xs">
                  {row.library_strategy_id
                    ? `${row.library_strategy_id}@${row.library_strategy_version ?? '?'}`
                    : 'Custom code'}
                </td>
                <td className="max-w-48 truncate px-3 py-2 font-mono text-xs">{row.strategy_hash}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {report.strategy_parameter_diffs.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-sm font-medium">Parameters</h4>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => setShowAllParams((current) => !current)}
            >
              {showAllParams ? 'Show differing only' : 'Show all parameters'}
            </Button>
          </div>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Parameter</th>
                  {report.runs.map((run) => (
                    <th key={run.run_id} className="px-3 py-2 font-medium">
                      Run {run.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {diffs.map((diff) => (
                  <tr
                    key={diff.name}
                    className={`border-t border-border ${diff.differs ? 'bg-amber-500/5' : ''}`}
                  >
                    <td className="px-3 py-2 font-medium">{diff.name}</td>
                    {diff.values.map((value, index) => (
                      <td key={`${diff.name}-${index}`} className="px-3 py-2 font-mono text-xs">
                        {value === null || value === undefined ? '—' : String(value)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {report.strategies_differ && (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          Strategy identity differs across runs. Check parameters and code snapshots before drawing
          conclusions.
        </p>
      )}
    </div>
  )
}
