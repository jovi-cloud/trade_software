import type { StrategyStatus } from './types'

interface StatusMeta {
  label: string
  className: string
}

/**
 * Status colouring is a domain decision (draft vs. validated should read
 * differently at a glance), so it is centralised here rather than inlined
 * at every call site - mirrors lib/colors.ts for pnl.
 */
const STATUS_META: Record<StrategyStatus, StatusMeta> = {
  draft: { label: 'Draft', className: 'border-transparent bg-muted text-muted-foreground' },
  testing: { label: 'Testing', className: 'border-transparent bg-primary text-primary-foreground' },
  validated: { label: 'Validated', className: 'border-transparent bg-profit/15 text-profit' },
  archived: { label: 'Archived', className: 'border-border text-muted-foreground' },
  rejected: { label: 'Rejected', className: 'border-transparent bg-loss/15 text-loss' },
}

export function statusMeta(status: StrategyStatus): StatusMeta {
  return STATUS_META[status]
}
