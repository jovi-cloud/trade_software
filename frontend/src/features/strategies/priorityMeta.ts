import type { Priority } from './types'

interface PriorityMeta {
  label: string
  className: string
}

const PRIORITY_META: Record<Priority, PriorityMeta> = {
  low: { label: 'Low priority', className: 'text-muted-foreground' },
  medium: { label: 'Medium priority', className: 'text-muted-foreground' },
  high: { label: 'High priority', className: 'font-medium text-foreground' },
}

export function priorityMeta(priority: Priority): PriorityMeta {
  return PRIORITY_META[priority]
}
