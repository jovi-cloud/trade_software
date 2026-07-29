import { Moon, Sun } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useHealth } from '@/features/system/queries'
import { useTheme } from '@/hooks/useTheme'
import { cn } from '@/lib/utils'

function BackendStatus() {
  const { data, isLoading, isError } = useHealth()

  const { label, dotClass } = isLoading
    ? { label: 'Connecting', dotClass: 'bg-muted-foreground animate-pulse' }
    : isError
      ? { label: 'Backend offline', dotClass: 'bg-loss' }
      : data?.status === 'ok'
        ? { label: `Backend v${data.version}`, dotClass: 'bg-profit' }
        : { label: 'Degraded', dotClass: 'bg-loss' }

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <span className={cn('size-2 rounded-full', dotClass)} />
      {label}
    </div>
  )
}

export function TopBar() {
  const { theme, toggleTheme } = useTheme()

  return (
    <header className="flex h-14 shrink-0 items-center justify-end gap-4 border-b border-border px-6">
      <BackendStatus />
      <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Toggle theme">
        {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
      </Button>
    </header>
  )
}
