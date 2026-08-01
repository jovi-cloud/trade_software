import { formatCurrency, formatTimestamp } from '@/lib/format'
import { pnlTextClass } from '@/lib/colors'

import type { ExecutionResult } from '../types'

interface TradeDetailsPanelProps {
  trade: ExecutionResult['trades'][number] | null
  onClose: () => void
}

export function TradeDetailsPanel({ trade, onClose }: TradeDetailsPanelProps) {
  if (!trade) return null

  return (
    <div className="rounded-md border border-border bg-card p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-4">
        <h3 className="text-sm font-medium">Trade #{trade.seq}</h3>
        <button
          type="button"
          onClick={onClose}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          Close
        </button>
      </div>
      <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
        <Detail label="Entry time" value={formatTimestamp(trade.entry_ts)} />
        <Detail label="Exit time" value={formatTimestamp(trade.exit_ts)} />
        <Detail label="Entry price" value={trade.entry_price.toFixed(4)} />
        <Detail label="Exit price" value={trade.exit_price.toFixed(4)} />
        <Detail label="Quantity" value={trade.quantity.toString()} />
        <Detail label="Profit before costs" value={formatCurrency(trade.gross_pnl)} />
        <Detail
          label="Profit after costs"
          value={formatCurrency(trade.net_pnl)}
          valueClassName={pnlTextClass(trade.net_pnl)}
        />
        <Detail label="Bars held" value={trade.bars_held.toString()} />
        {trade.exit_reason ? (
          <Detail label="Exit reason" value={trade.exit_reason.replaceAll('_', ' ')} />
        ) : null}
        {trade.initial_stop_level !== null && trade.initial_stop_level !== undefined ? (
          <Detail label="Initial stop" value={trade.initial_stop_level.toFixed(4)} />
        ) : null}
        {trade.trailing_stop_at_exit !== null && trade.trailing_stop_at_exit !== undefined ? (
          <Detail label="Trailing stop at exit" value={trade.trailing_stop_at_exit.toFixed(4)} />
        ) : null}
        {trade.highest_price_reached !== null && trade.highest_price_reached !== undefined ? (
          <Detail label="Highest price" value={trade.highest_price_reached.toFixed(4)} />
        ) : null}
        {trade.lowest_price_reached !== null && trade.lowest_price_reached !== undefined ? (
          <Detail label="Lowest price" value={trade.lowest_price_reached.toFixed(4)} />
        ) : null}
        {trade.max_profit !== null && trade.max_profit !== undefined ? (
          <Detail label="Max profit" value={formatCurrency(trade.max_profit)} />
        ) : null}
        {trade.max_drawdown_in_trade !== null && trade.max_drawdown_in_trade !== undefined ? (
          <Detail label="Max drawdown" value={formatCurrency(trade.max_drawdown_in_trade)} />
        ) : null}
        <Detail label="Commission" value={formatCurrency(trade.commission)} />
        <Detail label="Slippage" value={formatCurrency(trade.slippage_cost)} />
      </dl>
    </div>
  )
}

function Detail({
  label,
  value,
  valueClassName = '',
}: {
  label: string
  value: string
  valueClassName?: string
}) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className={`font-medium tabular ${valueClassName}`}>{value}</dd>
    </div>
  )
}
