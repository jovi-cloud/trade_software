import { Badge } from '@/components/ui/badge'

import { formatCurrency, formatNumber, formatTimestamp } from '@/lib/format'

import type { ExplainEvent } from '@/features/explain/api'

interface MetadataPanelProps {
  event: ExplainEvent
}

function MetadataRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium">{value}</dd>
    </div>
  )
}

export function MetadataPanel({ event }: MetadataPanelProps) {
  const rows: Array<{ label: string; value: string }> = []

  if (event.price !== null && event.price !== undefined) {
    rows.push({ label: 'Price', value: formatNumber(event.price, 4) })
  }
  if (event.quantity !== null && event.quantity !== undefined) {
    rows.push({ label: 'Quantity', value: formatNumber(event.quantity, 4) })
  }
  if (event.commission !== null && event.commission !== undefined) {
    rows.push({ label: 'Commission', value: formatCurrency(event.commission) })
  }
  if (event.slippage !== null && event.slippage !== undefined) {
    rows.push({ label: 'Slippage', value: formatCurrency(event.slippage) })
  }
  if (event.cash !== null && event.cash !== undefined) {
    rows.push({ label: 'Cash', value: formatCurrency(event.cash) })
  }
  if (event.portfolio_value !== null && event.portfolio_value !== undefined) {
    rows.push({ label: 'Portfolio', value: formatCurrency(event.portfolio_value) })
  }
  if (event.pnl !== null && event.pnl !== undefined) {
    rows.push({ label: 'P&L', value: formatCurrency(event.pnl) })
  }
  if (event.instrument) {
    rows.push({ label: 'Instrument', value: event.instrument })
  }
  if (event.timeframe) {
    rows.push({ label: 'Timeframe', value: event.timeframe })
  }

  const metadataEntries = Object.entries(event.metadata ?? {}).filter(
    ([, value]) => value !== null && value !== undefined,
  )

  return (
    <div className="space-y-3 rounded-md border border-border bg-muted/20 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">Schema v{event.schema_version ?? 1}</Badge>
        {event.timestamp_ms > 0 && (
          <span className="text-xs text-muted-foreground">
            {formatTimestamp(event.timestamp_ms)}
          </span>
        )}
      </div>
      <dl className="space-y-2">
        {rows.map((row) => (
          <MetadataRow key={row.label} label={row.label} value={row.value} />
        ))}
      </dl>
      {metadataEntries.length > 0 && (
        <div className="border-t border-border pt-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">Additional details</p>
          <dl className="space-y-2">
            {metadataEntries.map(([key, value]) => (
              <MetadataRow
                key={key}
                label={key.replace(/_/g, ' ')}
                value={typeof value === 'number' ? formatNumber(value) : String(value)}
              />
            ))}
          </dl>
        </div>
      )}
      <p className="text-sm text-muted-foreground">{event.message}</p>
    </div>
  )
}
