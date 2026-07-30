import type { ReactNode } from 'react'
import { useState } from 'react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { BarInspector } from '@/features/explain/components/BarInspector'
import { EventExplorer } from '@/features/explain/components/EventExplorer'
import { TradeInspector } from '@/features/explain/components/TradeInspector'

interface ExplainabilityPanelProps {
  runId: string
  tradeCount: number
  selectedBarIndex: number | null
  onBarSelect: (barIndex: number) => void
}

export function ExplainabilityPanel({
  runId,
  tradeCount,
  selectedBarIndex,
  onBarSelect,
}: ExplainabilityPanelProps) {
  const [activeTab, setActiveTab] = useState<'events' | 'trade' | 'bar'>('bar')
  const [selectedTradeId, setSelectedTradeId] = useState<number | null>(
    tradeCount > 0 ? 1 : null,
  )

  const tradeOptions = Array.from({ length: tradeCount }, (_, index) => index + 1)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <TabButton active={activeTab === 'bar'} onClick={() => setActiveTab('bar')}>
          Bar Inspector
        </TabButton>
        <TabButton active={activeTab === 'events'} onClick={() => setActiveTab('events')}>
          Event Explorer
        </TabButton>
        <TabButton
          active={activeTab === 'trade'}
          onClick={() => setActiveTab('trade')}
          disabled={tradeCount === 0}
        >
          Trade Inspector
        </TabButton>
      </div>

      {activeTab === 'bar' && (
        <BarInspector
          runId={runId}
          barIndex={selectedBarIndex}
          onNavigate={(barIndex) => {
            onBarSelect(barIndex)
          }}
        />
      )}

      {activeTab === 'events' && (
        <EventExplorer
          runId={runId}
          initialTradeId={selectedTradeId}
          onSelectTrade={(tradeId) => {
            setSelectedTradeId(tradeId)
            setActiveTab('trade')
          }}
        />
      )}

      {activeTab === 'trade' && (
        <div className="space-y-4">
          {tradeCount > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Select trade</CardTitle>
              </CardHeader>
              <CardContent className="max-w-xs">
                <Label className="sr-only">Trade</Label>
                <Select
                  value={String(selectedTradeId ?? 1)}
                  onValueChange={(value) => setSelectedTradeId(Number(value))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {tradeOptions.map((tradeId) => (
                      <SelectItem key={tradeId} value={String(tradeId)}>
                        Trade {tradeId}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </CardContent>
            </Card>
          )}
          {selectedTradeId && <TradeInspector runId={runId} tradeId={selectedTradeId} />}
        </div>
      )}
    </div>
  )
}

function TabButton({
  active,
  onClick,
  disabled,
  children,
}: {
  active: boolean
  onClick: () => void
  disabled?: boolean
  children: ReactNode
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
        active
          ? 'bg-primary text-primary-foreground'
          : 'bg-muted text-muted-foreground hover:bg-muted/80'
      } ${disabled ? 'cursor-not-allowed opacity-50' : ''}`}
    >
      {children}
    </button>
  )
}
