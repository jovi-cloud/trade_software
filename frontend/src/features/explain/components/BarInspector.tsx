import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ErrorState } from '@/components/common/ErrorState'
import { BarNavigationControls } from '@/features/explain/components/BarNavigation'
import {
  ConditionTable,
  DecisionSummary,
  ExecutionSummary,
} from '@/features/explain/components/ConditionTable'
import { MetadataPanel } from '@/features/explain/components/MetadataPanel'
import { OperandTable } from '@/features/explain/components/OperandTable'
import { EXPLAIN_EVENT_LABELS } from '@/features/explain/labels'
import { useBarInspection } from '@/features/explain/queries'
import { getErrorMessage } from '@/lib/apiClient'
import {
  formatCurrency,
  formatNumber,
  formatTimestamp,
} from '@/lib/format'

interface BarInspectorProps {
  runId: string
  barIndex: number | null
  onNavigate: (barIndex: number) => void
}

export function BarInspector({ runId, barIndex, onNavigate }: BarInspectorProps) {
  const { data, isLoading, isError, error } = useBarInspection(runId, barIndex)

  if (barIndex === null) {
    return (
      <Card>
        <CardContent className="py-8 text-sm text-muted-foreground">
          Click a candle on the chart to inspect what the engine knew on that bar.
        </CardContent>
      </Card>
    )
  }

  if (isLoading) {
    return <Skeleton className="h-96 w-full" />
  }

  if (isError || !data) {
    return (
      <ErrorState message={getErrorMessage(error, 'Unable to load bar inspection.')} />
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <CardTitle className="text-base">Bar {data.bar_index + 1} Inspector</CardTitle>
          <BarNavigationControls navigation={data.navigation} onNavigate={onNavigate} />
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-sm">
            <Metric label="Date / Time" value={formatTimestamp(data.candle.ts)} />
            <Metric label="Open" value={formatNumber(data.candle.open, 4)} />
            <Metric label="High" value={formatNumber(data.candle.high, 4)} />
            <Metric label="Low" value={formatNumber(data.candle.low, 4)} />
            <Metric label="Close" value={formatNumber(data.candle.close, 4)} />
            <Metric label="Volume" value={formatNumber(data.candle.volume, 0)} />
            <Metric
              label="Cash"
              value={
                data.market_state.cash !== null && data.market_state.cash !== undefined
                  ? formatCurrency(data.market_state.cash)
                  : '—'
              }
            />
            <Metric
              label="Portfolio"
              value={
                data.market_state.portfolio_value !== null &&
                data.market_state.portfolio_value !== undefined
                  ? formatCurrency(data.market_state.portfolio_value)
                  : '—'
              }
            />
          </dl>
        </CardContent>
      </Card>

      <DecisionInspector inspection={data} />
    </div>
  )
}

function DecisionInspector({ inspection }: { inspection: NonNullable<ReturnType<typeof useBarInspection>['data']> }) {
  const { market_state: market } = inspection

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Market State</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <dl className="grid gap-2 sm:grid-cols-2">
            <Metric label="Current Price" value={formatNumber(market.current_price, 4)} />
            <Metric label="Trend" value={market.trend} />
            <Metric label="Volatility" value={`${market.volatility_pct}%`} />
            <Metric label="Session" value={market.session} />
            <Metric label="Volume" value={formatNumber(market.volume, 0)} />
            <Metric
              label="Position"
              value={
                market.position
                  ? `${market.position.side} ${market.position.quantity} @ ${market.position.entry_price}`
                  : 'Flat'
              }
            />
          </dl>
          {Object.keys(market.indicators ?? {}).length > 0 && (
            <div>
              <p className="mb-2 text-xs font-medium text-muted-foreground">Indicators</p>
              <dl className="grid gap-2 sm:grid-cols-2">
                {Object.entries(market.indicators ?? {}).map(([name, value]) => (
                  <Metric key={name} label={name} value={String(value)} />
                ))}
              </dl>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Condition Evaluation</CardTitle>
        </CardHeader>
        <CardContent>
          <ConditionTable conditions={inspection.conditions} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Calculations</CardTitle>
        </CardHeader>
        <CardContent>
          <OperandTable operands={inspection.operands ?? []} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Decision</CardTitle>
        </CardHeader>
        <CardContent>
          <DecisionSummary decision={inspection.decision} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Execution</CardTitle>
        </CardHeader>
        <CardContent>
          <ExecutionSummary execution={inspection.execution} />
          <OrderList title="Open Orders" orders={inspection.open_orders} />
          <OrderList title="Filled Orders" orders={inspection.filled_orders} />
          <OrderList title="Rejected Orders" orders={inspection.cancelled_orders} />
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle className="text-base">Bar Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          {inspection.timeline.length === 0 ? (
            <p className="text-sm text-muted-foreground">No events recorded on this bar.</p>
          ) : (
            <ol className="space-y-2">
              {inspection.timeline.map((step) => (
                <li key={step.event_seq} className="rounded-md border border-border p-3 text-sm">
                  <div className="font-medium">
                    {formatTimestamp(step.timestamp_ms)} — {step.label}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {EXPLAIN_EVENT_LABELS[step.event_type] ?? step.event_type}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>

      {(inspection.explain_events?.length ?? 0) > 0 && (
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Event Metadata</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {(inspection.explain_events ?? []).map((event) => (
              <MetadataPanel key={event.event_id} event={event} />
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  )
}

function OrderList({
  title,
  orders,
}: {
  title: string
  orders: NonNullable<ReturnType<typeof useBarInspection>['data']>['open_orders']
}) {
  if (orders.length === 0) return null
  return (
    <div className="mt-4">
      <p className="mb-2 text-xs font-medium text-muted-foreground">{title}</p>
      <ul className="space-y-1 text-sm">
        {orders.map((order) => (
          <li key={order.order_ref}>
            {order.order_type} · {order.quantity} · {order.status}
          </li>
        ))}
      </ul>
    </div>
  )
}
