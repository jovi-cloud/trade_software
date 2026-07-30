import { ChevronRight } from 'lucide-react'
import { Link } from 'react-router-dom'

export interface Crumb {
  label: string
  /** Omit on the current page. */
  to?: string
}

interface BreadcrumbsProps {
  items: Crumb[]
}

/**
 * Where the trader is in the research workflow, and the way back to each step.
 *
 * The library -> configure -> run -> inspect path crosses four routes; without
 * this the only way back is the browser button, which loses the trail.
 */
export function Breadcrumbs({ items }: BreadcrumbsProps) {
  return (
    <nav aria-label="Breadcrumb" className="mb-3">
      <ol className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
        {items.map((item, index) => (
          <li key={`${item.label}-${item.to ?? 'current'}`} className="flex items-center gap-1">
            {index > 0 && <ChevronRight className="size-3 shrink-0" aria-hidden />}
            {item.to ? (
              <Link to={item.to} className="hover:text-foreground hover:underline">
                {item.label}
              </Link>
            ) : (
              <span className="font-medium text-foreground" aria-current="page">
                {item.label}
              </span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}
