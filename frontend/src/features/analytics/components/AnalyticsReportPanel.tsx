import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import type { AnalyticsReport, AnalyticsSection } from '../types'
import { ANALYTICS_SECTIONS } from '../types'
import { AnalyticsEquityChart } from './AnalyticsEquityChart'
import { DrawdownChart } from './DrawdownChart'
import { MetricGrid } from './MetricGrid'
import { MonthlyReturnsTable } from './MonthlyReturnsTable'
import { YearlyReturnsTable } from './YearlyReturnsTable'

interface AnalyticsReportPanelProps {
  analytics: AnalyticsReport
}

function SectionContent({ analytics, section }: { analytics: AnalyticsReport; section: AnalyticsSection }) {
  const { metrics, series } = analytics

  switch (section) {
    case 'overview':
      return <MetricGrid metrics={metrics} headlineOnly />
    case 'returns':
      return <MetricGrid metrics={metrics} category="returns" />
    case 'risk':
      return <MetricGrid metrics={metrics} category="risk" />
    case 'risk_adjusted':
      return <MetricGrid metrics={metrics} category="risk_adjusted" />
    case 'trades':
      return <MetricGrid metrics={metrics} category="trades" />
    case 'portfolio':
      return <MetricGrid metrics={metrics} category="portfolio" />
    case 'statistics':
      return <MetricGrid metrics={metrics} category="statistics" />
    case 'monthly':
      return <MonthlyReturnsTable rows={series.monthly_returns} />
    case 'yearly':
      return <YearlyReturnsTable rows={series.yearly_returns} />
    case 'drawdown':
      return (
        <DrawdownChart
          drawdownCurve={series.drawdown_curve}
          downsampled={series.curves_downsampled}
          maxDrawdownStartTs={series.max_drawdown_start_ts}
          maxDrawdownTroughTs={series.max_drawdown_trough_ts}
          maxDrawdownRecoveryTs={series.max_drawdown_recovery_ts}
        />
      )
    case 'equity':
      return (
        <AnalyticsEquityChart
          equityCurve={series.equity_curve}
          downsampled={series.curves_downsampled}
        />
      )
    default:
      return null
  }
}

export function AnalyticsReportPanel({ analytics }: AnalyticsReportPanelProps) {
  const [section, setSection] = useState<AnalyticsSection>('overview')
  const activeLabel = ANALYTICS_SECTIONS.find((item) => item.id === section)?.label ?? 'Overview'

  return (
    <Card>
      <CardHeader className="space-y-4">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="text-base">Performance &amp; Risk Analytics</CardTitle>
          <p className="text-xs text-muted-foreground">
            Analytics v{analytics.meta.analytics_version} · {analytics.meta.trading_days} trading days
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {ANALYTICS_SECTIONS.map((item) => (
            <Button
              key={item.id}
              type="button"
              size="sm"
              variant={section === item.id ? 'default' : 'outline'}
              onClick={() => setSection(item.id)}
            >
              {item.label}
            </Button>
          ))}
        </div>
      </CardHeader>
      <CardContent>
        <h3 className="mb-4 text-sm font-medium text-muted-foreground">{activeLabel}</h3>
        <SectionContent analytics={analytics} section={section} />
      </CardContent>
    </Card>
  )
}
