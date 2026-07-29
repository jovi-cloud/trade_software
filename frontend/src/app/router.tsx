import { lazy, Suspense } from 'react'
import { createBrowserRouter, type RouteObject } from 'react-router-dom'

import { AppShell } from '@/app/layout/AppShell'

// Route pages are lazy-loaded and therefore use default exports.
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))
const StrategyListPage = lazy(() => import('@/pages/strategies/StrategyListPage'))
const StrategyCreatePage = lazy(() => import('@/pages/strategies/StrategyCreatePage'))
const StrategyEditPage = lazy(() => import('@/pages/strategies/StrategyEditPage'))
const StrategyDetailPage = lazy(() => import('@/pages/strategies/StrategyDetailPage'))
const DataLibraryPage = lazy(() => import('@/pages/data/DataLibraryPage'))
const ImportDataPage = lazy(() => import('@/pages/data/ImportDataPage'))
const DatasetDetailPage = lazy(() => import('@/pages/data/DatasetDetailPage'))

function PageFallback() {
  return <div className="p-6 text-sm text-muted-foreground">Loading…</div>
}

const routes: RouteObject[] = [
  {
    path: '/',
    element: <AppShell />,
    children: [
      {
        index: true,
        element: (
          <Suspense fallback={<PageFallback />}>
            <DashboardPage />
          </Suspense>
        ),
      },
      {
        path: 'strategies',
        element: (
          <Suspense fallback={<PageFallback />}>
            <StrategyListPage />
          </Suspense>
        ),
      },
      {
        path: 'strategies/new',
        element: (
          <Suspense fallback={<PageFallback />}>
            <StrategyCreatePage />
          </Suspense>
        ),
      },
      {
        path: 'strategies/:id',
        element: (
          <Suspense fallback={<PageFallback />}>
            <StrategyDetailPage />
          </Suspense>
        ),
      },
      {
        path: 'strategies/:id/edit',
        element: (
          <Suspense fallback={<PageFallback />}>
            <StrategyEditPage />
          </Suspense>
        ),
      },
      {
        path: 'data',
        element: (
          <Suspense fallback={<PageFallback />}>
            <DataLibraryPage />
          </Suspense>
        ),
      },
      {
        path: 'data/import',
        element: (
          <Suspense fallback={<PageFallback />}>
            <ImportDataPage />
          </Suspense>
        ),
      },
      {
        path: 'data/:id',
        element: (
          <Suspense fallback={<PageFallback />}>
            <DatasetDetailPage />
          </Suspense>
        ),
      },
      // Phase 3: /backtests  Phase 4: /results  Phase 5: /notes
      {
        path: '*',
        element: (
          <Suspense fallback={<PageFallback />}>
            <NotFoundPage />
          </Suspense>
        ),
      },
    ],
  },
]

export const router = createBrowserRouter(routes)
