import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import type { ResearchInsight } from '../types'

interface InsightsPanelProps {
  insights: ResearchInsight[]
}

export function InsightsPanel({ insights }: InsightsPanelProps) {
  if (insights.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No automatic insights — metrics are tied or undefined across these runs.
      </p>
    )
  }

  return (
    <div className="grid gap-3 md:grid-cols-2">
      {insights.map((insight) => (
        <Card key={`${insight.metric_key}-${insight.run_id}`}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">{insight.metric_label}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">{insight.message}</CardContent>
        </Card>
      ))}
    </div>
  )
}
