import { BarChart3, Database, FlaskConical, History, LayoutDashboard, NotebookPen, Play } from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { cn } from '@/lib/utils'

interface NavItem {
  to: string
  label: string
  icon: typeof LayoutDashboard
  /** Routes land in later phases; shown but not yet navigable. */
  enabled: boolean
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, enabled: true },
  { to: '/strategies', label: 'Strategies', icon: FlaskConical, enabled: true },
  { to: '/data', label: 'Data', icon: Database, enabled: true },
  { to: '/backtests', label: 'Run Backtest', icon: Play, enabled: true },
  { to: '/backtests/runs', label: 'Runs', icon: History, enabled: true },
  { to: '/results', label: 'Results', icon: BarChart3, enabled: false },
  { to: '/notes', label: 'Notes', icon: NotebookPen, enabled: false },
]

export function Sidebar() {
  return (
    <aside className="flex w-56 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex h-14 items-center gap-2 px-4">
        <div className="flex size-7 items-center justify-center rounded-md bg-primary text-xs font-bold text-primary-foreground">
          TS
        </div>
        <span className="text-sm font-semibold text-sidebar-foreground">Research</span>
      </div>

      <nav className="flex flex-col gap-0.5 p-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon, enabled }) =>
          enabled ? (
            <NavLink
              key={to}
              to={to}
              end
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors',
                  isActive
                    ? 'bg-sidebar-accent font-medium text-sidebar-accent-foreground'
                    : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-foreground',
                )
              }
            >
              <Icon className="size-4" />
              {label}
            </NavLink>
          ) : (
            <span
              key={to}
              className="flex cursor-not-allowed items-center gap-2.5 rounded-md px-3 py-2 text-sm text-muted-foreground/40"
              title="Available in a later phase"
            >
              <Icon className="size-4" />
              {label}
            </span>
          ),
        )}
      </nav>
    </aside>
  )
}
