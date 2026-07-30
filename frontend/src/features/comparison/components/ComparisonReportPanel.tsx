import { Download } from 'lucide-react'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import { comparisonToCsv, comparisonToJson, downloadTextFile } from '../export'
import type { ComparisonReport, ComparisonSection } from '../types'
import { COMPARISON_SECTIONS } from '../types'
import { DatasetComparisonPanel } from './DatasetComparisonPanel'
import { DrawdownOverlayChart } from './DrawdownOverlayChart'
import { EquityOverlayChart } from './EquityOverlayChart'
import { ExecutionComparisonPanel } from './ExecutionComparisonPanel'
import { InsightsPanel } from './InsightsPanel'
import { MetricComparisonTable } from './MetricComparisonTable'
import { MonthlyComparisonTable } from './MonthlyComparisonTable'
import { StrategyComparisonPanel } from './StrategyComparisonPanel'

interface ComparisonReportPanelProps {
  report: ComparisonReport
}

function SectionBody({ report, section }: { report: ComparisonReport; section: ComparisonSection }) {
  switch (section) {
    case 'overview':
      return <MetricComparisonTable report={report} headlineOnly />
    case 'insights':
      return <InsightsPanel insights={report.insights} />
    case 'returns':
      return <MetricComparisonTable report={report} category="returns" />
    case 'risk':
      return <MetricComparisonTable report={report} category="risk" />
    case 'risk_adjusted':
      return <MetricComparisonTable report={report} category="risk_adjusted" />
    case 'trades':
      return <MetricComparisonTable report={report} category="trades" />
    case 'portfolio':
      return <MetricComparisonTable report={report} category="portfolio" />
    case 'statistics':
      return <MetricComparisonTable report={report} category="statistics" />
    case 'dataset':
      return <DatasetComparisonPanel report={report} />
    case 'strategy':
      return <StrategyComparisonPanel report={report} />
    case 'execution':
      return <ExecutionComparisonPanel report={report} />
    case 'equity':
      return <EquityOverlayChart overlays={report.equity_overlays} />
    case 'drawdown':
      return <DrawdownOverlayChart overlays={report.drawdown_overlays} />
    case 'monthly':
      return <MonthlyComparisonTable overlays={report.monthly_returns_overlays} />
    default:
      return null
  }
}

export function ComparisonReportPanel({ report }: ComparisonReportPanelProps) {
  const [section, setSection] = useState<ComparisonSection>('overview')
  const activeLabel = COMPARISON_SECTIONS.find((item) => item.id === section)?.label ?? 'Overview'

  const exportCsv = () => {
    downloadTextFile(
      `run-comparison-${report.runs.map((run) => run.label).join('-')}.csv`,
      comparisonToCsv(report),
      'text/csv;charset=utf-8',
    )
  }

  const exportJson = () => {
    downloadTextFile(
      `run-comparison-${report.runs.map((run) => run.label).join('-')}.json`,
      comparisonToJson(report),
      'application/json;charset=utf-8',
    )
  }

  return (
    <Card>
      <CardHeader className="space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle className="text-base">Run Comparison</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              Comparing {report.run_count} runs · v{report.comparison_version}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" variant="outline" onClick={exportCsv}>
              <Download className="size-4" />
              Export CSV
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={exportJson}>
              <Download className="size-4" />
              Export JSON
            </Button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {report.runs.map((run) => (
            <div key={run.run_id} className="rounded-md border border-border px-3 py-2 text-xs">
              <p className="font-medium">
                Run {run.label}: {run.strategy_name}
              </p>
              <p className="text-muted-foreground">{run.dataset_name}</p>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          {COMPARISON_SECTIONS.map((item) => (
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
        <SectionBody report={report} section={section} />
      </CardContent>
    </Card>
  )
}
