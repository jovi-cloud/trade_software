import { cn } from '@/lib/utils'

interface BrandMarkProps {
  compact?: boolean
  className?: string
}

export function BrandMark({ compact = false, className }: BrandMarkProps) {
  return (
    <div className={cn('flex items-center gap-2.5', className)}>
      <div
        className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-brand to-brand-secondary text-xs font-bold text-white shadow-sm"
        aria-hidden
      >
        TB
      </div>
      {!compact && (
        <div className="min-w-0 leading-tight">
          <p className="truncate text-sm font-semibold tracking-tight text-sidebar-foreground">
            Technobeala
          </p>
          <p className="truncate text-[11px] text-sidebar-foreground/60">Research Platform</p>
        </div>
      )}
    </div>
  )
}
