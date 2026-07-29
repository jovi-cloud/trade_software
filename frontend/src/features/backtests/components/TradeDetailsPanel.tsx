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
        <Detail label="Gross P&L" value={formatCurrency(trade.gross_pnl)} />
        <Detail
          label="Net P&L"
          value={formatCurrency(trade.net_pnl)}
          valueClassName={pnlTextClass(trade.net_pnl)}
        />
        <Detail label="Holding bars" value={trade.bars_held.toString()} />
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
