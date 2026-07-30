import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/common/ErrorState'
import {
  TRADE_OUTCOME_LABELS,
  formatReasonCode,
  formatTradeSide,
} from '@/features/explain/labels'
import { useTradeInspection } from '@/features/explain/queries'
import { getErrorMessage } from '@/lib/apiClient'
import {
  formatCurrency,
  formatNumber,
  formatPercent,
  formatTimestamp,
} from '@/lib/format'

interface TradeInspectorProps {
  runId: string
  tradeId: number
}

export function TradeInspector({ runId, tradeId }: TradeInspectorProps) {
  const { data, isLoading, isError, error } = useTradeInspection(runId, tradeId)

  if (isLoading) {
    return <Skeleton className="h-96 w-full" />
  }

  if (isError || !data) {
    return (
      <ErrorState message={getErrorMessage(error, 'Unable to load trade inspection.')} />
    )
  }

  const { summary, timeline } = data

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <CardTitle className="text-base">Trade {summary.trade_number} Summary</CardTitle>
          <Badge
            variant={
              summary.status === 'winning'
                ? 'default'
                : summary.status === 'losing'
                  ? 'destructive'
                  : 'secondary'
            }
          >
            {TRADE_OUTCOME_LABELS[summary.status]}
          </Badge>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-sm">
            <SummaryItem label="Direction" value={formatTradeSide(summary.direction)} />
            <SummaryItem
              label="Entry"
              value={`${formatTimestamp(summary.entry_time_ms)} @ ${formatNumber(summary.entry_price, 4)}`}
            />
            <SummaryItem
              label="Exit"
              value={`${formatTimestamp(summary.exit_time_ms)} @ ${formatNumber(summary.exit_price, 4)}`}
            />
            <SummaryItem label="Net Profit" value={formatCurrency(summary.net_profit)} />
            <SummaryItem label="Gross Profit" value={formatCurrency(summary.gross_profit)} />
            <SummaryItem label="Commission" value={formatCurrency(summary.commission)} />
            <SummaryItem label="Slippage" value={formatCurrency(summary.slippage)} />
            <SummaryItem
              label="Holding Period"
              value={`${summary.holding_period_bars} bars`}
            />
            <SummaryItem label="Return" value={formatPercent(summary.return_pct)} />
            <SummaryItem
              label="MAE"
              value={summary.mae !== null && summary.mae !== undefined ? formatCurrency(summary.mae) : '—'}
            />
            <SummaryItem
              label="MFE"
              value={summary.mfe !== null && summary.mfe !== undefined ? formatCurrency(summary.mfe) : '—'}
            />
            <SummaryItem
              label="Risk / Reward"
              value={
                summary.risk_reward !== null && summary.risk_reward !== undefined
                  ? formatNumber(summary.risk_reward, 2)
                  : '—'
              }
            />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Trade Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-3">
            {timeline.map((step) => (
              <li
                key={`${step.step_type}-${step.event_seq}`}
                className="rounded-md border border-border bg-muted/20 p-4"
              >
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="font-medium">{step.label}</span>
                  <Badge variant="outline">{formatReasonCode(step.reason_code)}</Badge>
                </div>
                <p className="text-sm text-muted-foreground">{step.message}</p>
                <dl className="mt-3 grid gap-2 text-xs text-muted-foreground sm:grid-cols-2 lg:grid-cols-4">
                  <div>
                    <dt className="inline">Time: </dt>
                    <dd className="inline">{formatTimestamp(step.timestamp_ms)}</dd>
                  </div>
                  {step.bar_index !== null && step.bar_index !== undefined && (
                    <div>
                      <dt className="inline">Bar: </dt>
                      <dd className="inline">{step.bar_index + 1}</dd>
                    </div>
                  )}
                  {step.price !== null && step.price !== undefined && (
                    <div>
                      <dt className="inline">Price: </dt>
                      <dd className="inline">{formatNumber(step.price, 4)}</dd>
                    </div>
                  )}
                  {step.quantity !== null && step.quantity !== undefined && (
                    <div>
                      <dt className="inline">Qty: </dt>
                      <dd className="inline">{formatNumber(step.quantity, 4)}</dd>
                    </div>
                  )}
                  {step.commission !== null && step.commission !== undefined && (
                    <div>
                      <dt className="inline">Commission: </dt>
                      <dd className="inline">{formatCurrency(step.commission)}</dd>
                    </div>
                  )}
                  {step.cash !== null && step.cash !== undefined && (
                    <div>
                      <dt className="inline">Cash: </dt>
                      <dd className="inline">{formatCurrency(step.cash)}</dd>
                    </div>
                  )}
                </dl>
                {step.related_event_seqs && step.related_event_seqs.length > 0 && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Related events: {step.related_event_seqs.join(', ')}
                  </p>
                )}
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </div>
  )
}

function SummaryItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  )
}
