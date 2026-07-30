import type { MetricCategory, MetricValue } from '../types'
import { MetricCard } from './MetricCard'

interface MetricGridProps {
  metrics: MetricValue[]
  category?: MetricCategory
  headlineOnly?: boolean
}

export function MetricGrid({ metrics, category, headlineOnly = false }: MetricGridProps) {
  const filtered = metrics.filter((metric) => {
    if (headlineOnly && !metric.is_headline) return false
    if (category && metric.category !== category) return false
    return true
  })

  if (filtered.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No metrics available for this section.
      </p>
    )
  }

  return (
    <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
      {filtered.map((metric) => (
        <MetricCard key={metric.key} metric={metric} />
      ))}
    </dl>
  )
}
