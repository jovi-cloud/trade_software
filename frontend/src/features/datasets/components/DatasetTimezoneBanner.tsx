import { AlertTriangle } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { DEFAULT_EXCHANGE_TIMEZONE } from '@/lib/format'

import { useRevalidateDataset } from '../queries'
import type { Dataset } from '../types'

const INDIAN_EXCHANGES = new Set(['NSE', 'BSE', 'NFO', 'BFO', 'MCX'])

function likelyIndianDataset(dataset: Dataset): boolean {
  return INDIAN_EXCHANGES.has(dataset.exchange.trim().toUpperCase())
}

interface DatasetTimezoneBannerProps {
  dataset: Dataset
  onFixed?: () => void
}

export function DatasetTimezoneBanner({ dataset, onFixed }: DatasetTimezoneBannerProps) {
  const revalidate = useRevalidateDataset()

  if (dataset.timezone !== 'UTC' || !likelyIndianDataset(dataset)) {
    return null
  }

  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm">
      <div className="flex min-w-0 items-start gap-2">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" />
        <div>
          <p className="font-medium text-foreground">Bar timestamps may be shifted by 5h 30m</p>
          <p className="mt-1 text-muted-foreground">
            This dataset was imported as UTC, but {dataset.exchange} data is usually in{' '}
            {DEFAULT_EXCHANGE_TIMEZONE}. Trade and bar times in backtests will look wrong (for
            example 2:05 pm showing as 7:35 pm) until you re-process with the correct timezone.
          </p>
        </div>
      </div>
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={revalidate.isPending}
        onClick={() =>
          revalidate.mutate(
            { id: dataset.id, timezone: DEFAULT_EXCHANGE_TIMEZONE },
            { onSuccess: () => onFixed?.() },
          )
        }
      >
        {revalidate.isPending ? 'Re-processing…' : `Fix to ${DEFAULT_EXCHANGE_TIMEZONE}`}
      </Button>
    </div>
  )
}
