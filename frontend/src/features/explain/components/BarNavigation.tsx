import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

import type { BarInspection } from '@/features/explain/api'

interface BarNavigationProps {
  navigation: BarInspection['navigation']
  onNavigate: (barIndex: number) => void
}

export function BarNavigationControls({ navigation, onNavigate }: BarNavigationProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={navigation.previous_bar_index === null || navigation.previous_bar_index === undefined}
        onClick={() => {
          if (navigation.previous_bar_index !== null && navigation.previous_bar_index !== undefined) {
            onNavigate(navigation.previous_bar_index)
          }
        }}
      >
        Previous Bar
      </Button>
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={navigation.next_bar_index === null || navigation.next_bar_index === undefined}
        onClick={() => {
          if (navigation.next_bar_index !== null && navigation.next_bar_index !== undefined) {
            onNavigate(navigation.next_bar_index)
          }
        }}
      >
        Next Bar
      </Button>
      <JumpToBarInput barCount={navigation.bar_count} onNavigate={onNavigate} />
      {navigation.first_signal_bar !== null && navigation.first_signal_bar !== undefined && (
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() => onNavigate(navigation.first_signal_bar!)}
        >
          First Signal
        </Button>
      )}
      {navigation.last_signal_bar !== null && navigation.last_signal_bar !== undefined && (
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() => onNavigate(navigation.last_signal_bar!)}
        >
          Last Signal
        </Button>
      )}
      {(navigation.trade_entry_bars?.length ?? 0) > 0 && (
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() => onNavigate(navigation.trade_entry_bars![0]!)}
        >
          Trade Entry
        </Button>
      )}
      {(navigation.trade_exit_bars?.length ?? 0) > 0 && (
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() => onNavigate(navigation.trade_exit_bars!.at(-1)!)}
        >
          Trade Exit
        </Button>
      )}
    </div>
  )
}

function JumpToBarInput({
  barCount,
  onNavigate,
}: {
  barCount: number
  onNavigate: (barIndex: number) => void
}) {
  return (
    <form
      className="flex items-end gap-2"
      onSubmit={(event) => {
        event.preventDefault()
        const data = new FormData(event.currentTarget)
        const raw = Number(data.get('barNumber'))
        if (!Number.isFinite(raw)) return
        const barIndex = Math.max(0, Math.min(barCount - 1, Math.round(raw) - 1))
        onNavigate(barIndex)
      }}
    >
      <div>
        <Label htmlFor="jump-bar" className="sr-only">
          Jump to bar
        </Label>
        <Input id="jump-bar" name="barNumber" type="number" min={1} max={barCount} className="h-8 w-24" />
      </div>
      <Button type="submit" size="sm" variant="outline">
        Jump
      </Button>
    </form>
  )
}
