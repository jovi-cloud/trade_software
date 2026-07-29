import type { ReactNode } from 'react'

interface ChartContainerProps {
  children: ReactNode
  className?: string
  height?: number
}

export function ChartContainer({ children, className = '', height = 420 }: ChartContainerProps) {
  return (
    <div
      className={`relative w-full overflow-hidden rounded-md border border-border ${className}`}
      style={{ height }}
    >
      {children}
    </div>
  )
}
