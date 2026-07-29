import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatCurrency, formatInteger, formatPercent } from '@/lib/format'

import type { ExecutionResult } from '../types'

interface PerformanceSummaryProps {
  metrics: ExecutionResult['metrics']
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-lg font-medium">{value}</dd>
    </div>
  )
}

export function PerformanceSummary({ metrics }: PerformanceSummaryProps) {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Performance Summary</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <MetricTile label="Net Profit" value={formatCurrency(metrics.net_profit)} />
            <MetricTile label="Return %" value={formatPercent(metrics.return_pct)} />
            <MetricTile
              label="Profit Factor"
              value={
                metrics.profit_factor > 0 ? metrics.profit_factor.toFixed(2) : '—'
              }
            />
            <MetricTile label="Win Rate" value={formatPercent(metrics.win_rate_pct)} />
            <MetricTile label="Expectancy" value={formatCurrency(metrics.expectancy)} />
            <MetricTile label="Average Trade" value={formatCurrency(metrics.average_trade)} />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Trade Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricTile
              label="Winning Trades"
              value={formatInteger(metrics.winning_trades)}
            />
            <MetricTile label="Losing Trades" value={formatInteger(metrics.losing_trades)} />
            <MetricTile label="Largest Win" value={formatCurrency(metrics.largest_win)} />
            <MetricTile label="Largest Loss" value={formatCurrency(metrics.largest_loss)} />
            <MetricTile label="Average Win" value={formatCurrency(metrics.average_win)} />
            <MetricTile label="Average Loss" value={formatCurrency(metrics.average_loss)} />
            <MetricTile label="Commission" value={formatCurrency(metrics.commission_paid)} />
            <MetricTile label="Slippage" value={formatCurrency(metrics.slippage_cost)} />
          </dl>
        </CardContent>
      </Card>
    </div>
  )
}
