import {
  BarChart3,
  BookOpen,
  Database,
  FlaskConical,
  GitCompare,
  History,
  LayoutDashboard,
  NotebookPen,
  Play,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'

import { BrandMark } from '@/components/common/BrandMark'
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
  { to: '/strategy-library', label: 'Strategy Library', icon: BookOpen, enabled: true },
  { to: '/strategies', label: 'Strategies', icon: FlaskConical, enabled: true },
  { to: '/data', label: 'Data', icon: Database, enabled: true },
  { to: '/backtests', label: 'Run Backtest', icon: Play, enabled: true },
  { to: '/backtests/runs', label: 'Runs', icon: History, enabled: true },
  { to: '/backtests/compare', label: 'Compare', icon: GitCompare, enabled: true },
  { to: '/results', label: 'Results', icon: BarChart3, enabled: false },
  { to: '/notes', label: 'Notes', icon: NotebookPen, enabled: false },
]

export function Sidebar() {
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="border-b border-sidebar-border px-4 py-4">
        <BrandMark />
      </div>

      <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-2">
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
                    ? 'bg-sidebar-accent font-medium text-sidebar-primary shadow-sm ring-1 ring-sidebar-border/60'
                    : 'text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-foreground',
                )
              }
            >
              <Icon className="size-4 shrink-0" />
              {label}
            </NavLink>
          ) : (
            <span
              key={to}
              className="flex cursor-not-allowed items-center gap-2.5 rounded-md px-3 py-2 text-sm text-sidebar-foreground/30"
              title="Available in a later phase"
            >
              <Icon className="size-4" />
              {label}
            </span>
          ),
        )}
      </nav>

      <footer className="border-t border-sidebar-border px-4 py-3">
        <p className="text-[11px] leading-relaxed text-sidebar-foreground/50">
          Built by{' '}
          <span className="font-medium text-sidebar-primary">Technobeala</span>
        </p>
        <p className="mt-0.5 text-[10px] text-sidebar-foreground/35">
          Strategy research &amp; backtesting
        </p>
      </footer>
    </aside>
  )
}
