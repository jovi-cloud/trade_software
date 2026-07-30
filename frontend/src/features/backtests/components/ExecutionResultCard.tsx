import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ExecutionTimeline } from '@/features/explain/components/ExecutionTimeline'
import {
  formatOrderStatus,
  formatOrderType,
  formatTradeSide,
} from '@/features/explain/labels'
import { formatCurrency, formatDuration, formatInteger, formatTimestamp } from '@/lib/format'

import type { ExecutionResult } from '../types'
import { BacktestChartTabs } from './BacktestChartTabs'
import { PerformanceSummary } from './PerformanceSummary'

interface ExecutionResultCardProps {
  result: ExecutionResult
  selectedBarIndex?: number | null
  onBarSelect?: (barIndex: number) => void
}

export function ExecutionResultCard({
  result,
  selectedBarIndex,
  onBarSelect,
}: ExecutionResultCardProps) {
  return (
    <div className="max-w-6xl space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <CardTitle className="text-base">Backtest completed</CardTitle>
          <Badge variant={result.completed ? 'default' : 'destructive'}>
            {result.completed ? 'Success' : 'Failed'}
          </Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-xs text-muted-foreground">Price bars analysed</dt>
              <dd className="text-lg font-medium">{formatInteger(result.bars_processed)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Run duration</dt>
              <dd className="text-lg font-medium">{formatDuration(result.execution_time_ms)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Trades completed</dt>
              <dd className="text-lg font-medium">{formatInteger(result.trade_count)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">Ending balance</dt>
              <dd className="text-lg font-medium">{formatCurrency(result.final_cash)}</dd>
            </div>
          </dl>

          {!result.position_closed && (
            <p className="text-sm text-amber-600 dark:text-amber-400">
              This run ended with an open position that was not closed.
            </p>
          )}
        </CardContent>
      </Card>

      <ExecutionTimeline events={result.explain_events ?? []} />

      <PerformanceSummary metrics={result.metrics} />

      <BacktestChartTabs
        result={result}
        selectedBarIndex={selectedBarIndex}
        onBarSelect={onBarSelect}
      />

      {result.trades.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-sm font-medium">Trade history</h3>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">#</th>
                  <th className="px-3 py-2 font-medium">Direction</th>
                  <th className="px-3 py-2 font-medium">Qty</th>
                  <th className="px-3 py-2 font-medium">Entry</th>
                  <th className="px-3 py-2 font-medium">Exit</th>
                  <th className="px-3 py-2 font-medium">Profit after costs</th>
                </tr>
              </thead>
              <tbody>
                {result.trades.map((trade) => (
                  <tr key={trade.seq} className="border-t border-border">
                    <td className="px-3 py-2">{trade.seq}</td>
                    <td className="px-3 py-2">{formatTradeSide(trade.side)}</td>
                    <td className="px-3 py-2">{trade.quantity}</td>
                    <td className="px-3 py-2">
                      {formatTimestamp(trade.entry_ts)} @ {trade.entry_price.toFixed(4)}
                    </td>
                    <td className="px-3 py-2">
                      {formatTimestamp(trade.exit_ts)} @ {trade.exit_price.toFixed(4)}
                    </td>
                    <td
                      className={`px-3 py-2 font-medium ${
                        trade.net_pnl >= 0 ? 'text-emerald-600' : 'text-red-600'
                      }`}
                    >
                      {formatCurrency(trade.net_pnl)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {result.orders.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-sm font-medium">Orders</h3>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Order</th>
                  <th className="px-3 py-2 font-medium">Type</th>
                  <th className="px-3 py-2 font-medium">Qty</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Fill price</th>
                  <th className="px-3 py-2 font-medium">Commission</th>
                </tr>
              </thead>
              <tbody>
                {result.orders.map((order) => (
                  <tr key={order.id} className="border-t border-border">
                    <td className="px-3 py-2">#{order.id}</td>
                    <td className="px-3 py-2">{formatOrderType(order.order_type)}</td>
                    <td className="px-3 py-2">{order.quantity}</td>
                    <td className="px-3 py-2">{formatOrderStatus(order.status)}</td>
                    <td className="px-3 py-2">
                      {order.fill_price !== null && order.fill_price !== undefined
                        ? order.fill_price.toFixed(4)
                        : '—'}
                    </td>
                    <td className="px-3 py-2">{formatCurrency(order.commission)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {result.warnings.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-sm font-medium">Warnings</h3>
          <ul className="space-y-1 rounded-md border border-border bg-muted/30 p-3 text-sm">
            {result.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </section>
      )}

      {result.errors.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-sm font-medium text-destructive">Errors</h3>
          <ul className="space-y-1 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
            {result.errors.map((error) => (
              <li key={error}>{error}</li>
            ))}
          </ul>
        </section>
      )}

      {result.strategy_logs.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-sm font-medium">Strategy notes during run</h3>
          <pre className="max-h-64 overflow-auto rounded-md border border-border bg-muted/30 p-3 text-xs">
            {result.strategy_logs.join('\n')}
          </pre>
        </section>
      )}
    </div>
  )
}
