import { Outlet } from 'react-router-dom'

import { Sidebar } from '@/app/layout/Sidebar'
import { TopBar } from '@/app/layout/TopBar'

export function AppShell() {
  return (
    <div className="flex h-full min-h-0 overflow-hidden bg-background">
      <Sidebar />
      <div className="flex min-h-0 min-w-0 flex-1 flex-col bg-background">
        <TopBar />
        <main className="app-surface relative min-h-0 flex-1 overflow-y-auto overscroll-none px-6 py-6">
          <div className="relative w-full pb-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
