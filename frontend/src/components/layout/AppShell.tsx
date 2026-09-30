import { ChevronRight, FlaskConical, Home } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'

import { useSession } from '@/app/session'
import { useDocumentTitle, useRouteMeta, type Crumb } from '@/components/layout/route-meta'
import { Sidebar } from '@/components/layout/Sidebar'
import { TopBar } from '@/components/layout/TopBar'
import { LoadingState } from '@/components/states'
import { useDemoState } from '@/lib/demo/store'

function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }) {
  if (crumbs.length === 0) return null
  return (
    <nav aria-label="Breadcrumb" className="mb-4">
      <ol className="flex flex-wrap items-center gap-1 text-sm text-muted-foreground">
        <li>
          <Link to="/dashboard" className="inline-flex items-center rounded hover:text-foreground focus-visible:outline-2" aria-label="Overview">
            <Home className="size-3.5" aria-hidden />
          </Link>
        </li>
        {crumbs.map((crumb, index) => (
          <li key={crumb.to} className="inline-flex items-center gap-1">
            <ChevronRight className="size-3.5" aria-hidden />
            {index === crumbs.length - 1 ? (
              <span aria-current="page" className="font-medium text-foreground">
                {crumb.label}
              </span>
            ) : (
              <Link to={crumb.to} className="rounded hover:text-foreground focus-visible:outline-2">
                {crumb.label}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}

function DemoStrip() {
  const { mode } = useSession()
  const demo = useDemoState()
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b bg-demo-soft px-4 py-1.5 text-xs text-demo lg:px-8">
      <span className="inline-flex items-center gap-1.5 font-semibold">
        <FlaskConical className="size-3.5" aria-hidden /> Demo prototype
      </span>
      <span className="text-demo/80">
        All figures come from a synthetic demo world, not real or official statistics.
      </span>
      <span className="ml-auto font-medium">
        {mode === 'api' ? 'Connected to the KaushalSetu API' : 'Offline demo mode (no API)'}
        {demo.evExpansionSimulated ? ' · Nashik EV expansion simulated' : ''}
      </span>
    </div>
  )
}

export function AppShell() {
  const { t } = useTranslation()
  const { user, ready } = useSession()
  const location = useLocation()
  const { titleKey, crumbs } = useRouteMeta()
  const title = titleKey ? t(titleKey) : t('app.name')
  useDocumentTitle(title)

  if (!ready) return <LoadingState className="p-8" />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />

  return (
    <div className="min-h-screen bg-background">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-primary px-3 py-2 text-primary-foreground focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Skip to content
      </a>
      <Sidebar />
      <div className="lg:pl-64">
        <TopBar title={title} />
        <DemoStrip />
        <main id="main" tabIndex={-1} className="mx-auto max-w-[1600px] px-4 py-6 outline-none lg:px-8 lg:py-8">
          <Breadcrumbs crumbs={crumbs} />
          <Outlet />
        </main>
      </div>
    </div>
  )
}
