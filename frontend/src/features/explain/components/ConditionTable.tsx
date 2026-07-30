import { Badge } from '@/components/ui/badge'

import { formatReasonCode } from '@/features/explain/labels'
import type { BarInspection } from '@/features/explain/api'

interface ConditionTableProps {
  conditions: BarInspection['conditions']
}

export function ConditionTable({ conditions }: ConditionTableProps) {
  if (conditions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No strategy conditions were traced on this bar. Engine portfolio checks may still apply.
      </p>
    )
  }

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full text-left text-sm">
        <thead className="bg-muted/40 text-xs text-muted-foreground">
          <tr>
            <th className="px-3 py-2 font-medium">Condition</th>
            <th className="px-3 py-2 font-medium">Actual</th>
            <th className="px-3 py-2 font-medium">Expected</th>
            <th className="px-3 py-2 font-medium">Result</th>
          </tr>
        </thead>
        <tbody>
          {conditions.map((condition) => {
            // A rule that was never consulted is not a failing rule. Rendering
            // both as red is what made "why didn't my crossover fire" unanswerable
            // on the bars where a position was already open.
            const unevaluated = condition.evaluated === false
            return (
              <tr
                key={condition.name}
                className={`border-t border-border ${unevaluated ? 'text-muted-foreground' : ''}`}
              >
                <td className="px-3 py-2 font-medium">{condition.name}</td>
                <td className="px-3 py-2">{condition.actual_value}</td>
                <td className="px-3 py-2">{condition.expected_value}</td>
                <td className="px-3 py-2">
                  <Badge
                    variant={
                      unevaluated ? 'outline' : condition.passed ? 'default' : 'destructive'
                    }
                  >
                    {unevaluated ? 'Not reached' : condition.passed ? 'True' : 'False'}
                  </Badge>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function DecisionSummary({ decision }: { decision: BarInspection['decision'] }) {
  return (
    <div className="space-y-2 rounded-md border border-border bg-muted/20 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">Decision</span>
        <Badge variant="outline">{formatDecisionType(decision.decision_type)}</Badge>
      </div>
      <p className="text-sm">
        <span className="text-muted-foreground">Reason: </span>
        {formatReasonCode(decision.reason_code)}
      </p>
      <p className="text-sm text-muted-foreground">{decision.message}</p>
    </div>
  )
}

export function ExecutionSummary({ execution }: { execution: BarInspection['execution'] }) {
  return (
    <div className="space-y-2 rounded-md border border-border bg-muted/20 p-4 text-sm">
      <p className="font-medium">Execution</p>
      <p className="text-muted-foreground">{execution.message}</p>
      {execution.occurred && execution.fill_price !== null && execution.fill_price !== undefined && (
        <dl className="grid gap-2 sm:grid-cols-2">
          <div>
            <dt className="text-xs text-muted-foreground">Fill price</dt>
            <dd>{execution.fill_price}</dd>
          </div>
          {execution.commission !== null && execution.commission !== undefined && (
            <div>
              <dt className="text-xs text-muted-foreground">Commission</dt>
              <dd>{execution.commission}</dd>
            </div>
          )}
        </dl>
      )}
    </div>
  )
}

function formatDecisionType(value: string): string {
  switch (value) {
    case 'buy':
      return 'Buy'
    case 'sell':
      return 'Sell'
    case 'hold':
      return 'Hold'
    case 'exit':
      return 'Exit'
    case 'no_trade':
      return 'No Trade'
    case 'rejected':
      return 'Rejected'
    default:
      return value
  }
}
