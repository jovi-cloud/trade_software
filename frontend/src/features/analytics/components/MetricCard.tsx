import { Info } from 'lucide-react'

import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

import { formatMetricValue, metricValueTone } from '../formatMetric'
import type { MetricValue } from '../types'

interface MetricCardProps {
  metric: MetricValue
}

export function MetricCard({ metric }: MetricCardProps) {
  const display = formatMetricValue(metric.value, metric.format, metric.precision)
  const tone = metricValueTone(metric.value, metric.higher_is_better)

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-1 flex items-center gap-1.5">
        <dt className="text-xs text-muted-foreground">{metric.label}</dt>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                className="text-muted-foreground hover:text-foreground"
                aria-label={`About ${metric.label}`}
              >
                <Info className="size-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent>{metric.description}</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      <dd className={`text-lg font-semibold tabular-nums ${tone}`}>{display}</dd>
    </div>
  )
}
