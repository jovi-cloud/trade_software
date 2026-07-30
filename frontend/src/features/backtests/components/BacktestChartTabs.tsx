import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

import type { ExecutionResult } from '../types'
import { BacktestChart } from './BacktestChart'
import { EquityChart } from './EquityChart'

type ChartTab = 'price' | 'equity'

interface BacktestChartTabsProps {
  result: ExecutionResult
  selectedBarIndex?: number | null
  onBarSelect?: (barIndex: number) => void
}

export function BacktestChartTabs({
  result,
  selectedBarIndex,
  onBarSelect,
}: BacktestChartTabsProps) {
  const [tab, setTab] = useState<ChartTab>('price')

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <CardTitle className="text-base">Chart</CardTitle>
        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            variant={tab === 'price' ? 'default' : 'outline'}
            onClick={() => setTab('price')}
          >
            Price Chart
          </Button>
          <Button
            type="button"
            size="sm"
            variant={tab === 'equity' ? 'default' : 'outline'}
            onClick={() => setTab('equity')}
          >
            Equity Curve
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {tab === 'price' ? (
          <BacktestChart
            result={result}
            selectedBarIndex={selectedBarIndex}
            onBarSelect={onBarSelect}
          />
        ) : (
          <EquityChart equityHistory={result.equity_history} />
        )}
      </CardContent>
    </Card>
  )
}
