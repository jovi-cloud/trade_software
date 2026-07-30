import { Badge } from '@/components/ui/badge'
import { formatDate } from '@/lib/format'

import type { ComparisonReport } from '../types'

interface DatasetComparisonPanelProps {
  report: ComparisonReport
}

export function DatasetComparisonPanel({ report }: DatasetComparisonPanelProps) {
  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-sm">
        <thead className="bg-muted/40 text-xs text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-medium">Run</th>
            <th className="px-3 py-2 font-medium">Dataset</th>
            <th className="px-3 py-2 font-medium">Version</th>
            <th className="px-3 py-2 font-medium">Fingerprint</th>
            <th className="px-3 py-2 font-medium">Imported</th>
            <th className="px-3 py-2 font-medium">Quality</th>
          </tr>
        </thead>
        <tbody>
          {report.dataset_rows.map((row) => (
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
              <td className="px-3 py-2">{row.dataset_name}</td>
              <td className="px-3 py-2">
                {row.dataset_version_number !== null ? `v${row.dataset_version_number}` : '—'}
              </td>
              <td className="max-w-48 truncate px-3 py-2 font-mono text-xs">{row.dataset_hash}</td>
              <td className="px-3 py-2">
                {row.dataset_imported_at ? formatDate(row.dataset_imported_at) : '—'}
              </td>
              <td className="px-3 py-2">{row.dataset_quality_score ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {report.datasets_differ && (
        <p className="border-t border-border px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
          These runs use different datasets or versions. Compare metrics with care.
        </p>
      )}
    </div>
  )
}
