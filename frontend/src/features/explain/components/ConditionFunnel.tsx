import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import { useDecisionSummary } from '@/features/explain/queries'

interface ConditionFunnelProps {
  runId: string
}

/**
 * Whole-run condition tallies: how often each rule was reached, how often it passed.
 *
 * The first thing to read on a run that produced no trades. A condition reached
 * thousands of times and never satisfied is the exact point the strategy stopped,
 * and it is visible here without opening a single bar. On the run that prompted
 * this feature, `Position Size Available` read 3,707 reached / 0 passed.
 */
export function ConditionFunnel({ runId }: ConditionFunnelProps) {
  const { data, isPending, isError, error } = useDecisionSummary(runId)

  if (isPending) {
    return <p className="text-sm text-muted-foreground">Loading condition tallies…</p>
  }
  if (isError) {
    return (
      <p className="text-sm text-destructive">
        {error instanceof Error ? error.message : 'Could not load the decision log.'}
      </p>
    )
  }

  const conditions = data.conditions ?? []
  const blockers = conditions.filter((item) => item.evaluated > 0 && item.passed === 0)

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">
          Condition tallies
          <span className="ml-2 font-normal text-muted-foreground">
            {data.total_rows.toLocaleString()} bars
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {blockers.length > 0 && (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">
            <p className="font-medium">
              {blockers.length === 1 ? 'One condition' : `${blockers.length} conditions`} never
              passed
            </p>
            <p className="text-muted-foreground">
              {blockers.map((item) => item.name).join(', ')} — reached, but never satisfied on any
              bar. This is where the strategy stopped.
            </p>
          </div>
        )}

        <div className="overflow-x-auto rounded-md border border-border">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/40 text-xs text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Condition</th>
                <th className="px-3 py-2 font-medium">Expected</th>
                <th className="px-3 py-2 text-right font-medium">Reached</th>
                <th className="px-3 py-2 text-right font-medium">Passed</th>
                <th className="px-3 py-2 text-right font-medium">Pass rate</th>
              </tr>
            </thead>
            <tbody>
              {conditions.map((item) => {
                const rate = item.evaluated === 0 ? null : item.passed / item.evaluated
                const dead = item.evaluated > 0 && item.passed === 0
                return (
                  <tr
                    key={item.name}
                    className={`border-t border-border ${dead ? 'bg-destructive/5' : ''}`}
                  >
                    <td className="px-3 py-2 font-medium">{item.name}</td>
                    <td className="px-3 py-2 text-muted-foreground">{item.expected}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">
                      {item.evaluated.toLocaleString()}
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">
                      {item.passed.toLocaleString()}
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">
                      {rate === null ? '—' : `${(rate * 100).toFixed(1)}%`}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <p className="text-xs text-muted-foreground">
          &ldquo;Reached&rdquo; counts the bars on which the rule was actually consulted. A rule
          below an earlier failing rule is never reached, which is why the counts differ.
        </p>
      </CardContent>
    </Card>
  )
}
