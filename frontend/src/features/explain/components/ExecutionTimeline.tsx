import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatTimestamp } from '@/lib/format'

import {
  EXPLAIN_EVENT_LABELS,
  EXPLAIN_LAYER_LABELS,
  STATUS_LABELS,
  formatOrderRef,
  formatPositionRef,
  formatTradeNumber,
} from '@/features/explain/labels'

import type { components } from '@/types/api'

type ExplainEventRead = components['schemas']['ExplainEventRead']

interface ExecutionTimelineProps {
  events: ExplainEventRead[]
}

const STATUS_VARIANT: Record<
  ExplainEventRead['status'],
  'default' | 'secondary' | 'destructive' | 'outline'
> = {
  ok: 'default',
  info: 'secondary',
  warning: 'outline',
  rejected: 'destructive',
  failed: 'destructive',
}

export function ExecutionTimeline({ events }: ExecutionTimelineProps) {
  const timelineEvents = events.filter(
    (event) => event.layer !== 'narrative' && event.event_type !== 'human_narrative',
  )

  if (timelineEvents.length === 0) {
    return null
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Execution Timeline</CardTitle>
      </CardHeader>
      <CardContent>
        <ol className="space-y-3">
          {timelineEvents.map((event) => (
            <li
              key={event.event_id ?? event.seq}
              className="rounded-md border border-border bg-muted/20 p-3 text-sm"
            >
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="font-medium">
                  {EXPLAIN_EVENT_LABELS[event.event_type] ?? event.event_type}
                </span>
                <Badge variant={STATUS_VARIANT[event.status]}>
                  {STATUS_LABELS[event.status]}
                </Badge>
                <Badge variant="outline">{EXPLAIN_LAYER_LABELS[event.layer]}</Badge>
              </div>
              <p className="text-muted-foreground">{event.message}</p>
              <dl className="mt-2 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2 lg:grid-cols-4">
                {event.timestamp_ms > 0 && (
                  <div>
                    <dt className="inline">Time: </dt>
                    <dd className="inline">{formatTimestamp(event.timestamp_ms)}</dd>
                  </div>
                )}
                {event.bar_index !== null && event.bar_index !== undefined && (
                  <div>
                    <dt className="inline">Bar: </dt>
                    <dd className="inline">{event.bar_index + 1}</dd>
                  </div>
                )}
                {event.order_id !== null && event.order_id !== undefined && (
                  <div>
                    <dt className="inline">Order: </dt>
                    <dd className="inline">{formatOrderRef(event.order_id)}</dd>
                  </div>
                )}
                {(event.trade_id ?? event.trade_seq) !== null &&
                  (event.trade_id ?? event.trade_seq) !== undefined && (
                    <div>
                      <dt className="inline">Trade: </dt>
                      <dd className="inline">
                        {formatTradeNumber(event.trade_id ?? event.trade_seq)}
                      </dd>
                    </div>
                  )}
                {event.position_id !== null && event.position_id !== undefined && (
                  <div>
                    <dt className="inline">Position: </dt>
                    <dd className="inline">{formatPositionRef(event.position_id)}</dd>
                  </div>
                )}
              </dl>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}
