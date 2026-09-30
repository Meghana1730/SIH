import { useTranslation } from 'react-i18next'
import { NavLink } from 'react-router-dom'

import { FOOTER_NAV, MAIN_NAV, type NavItem } from '@/components/layout/nav'
import { useRecommendations } from '@/lib/api/queries'
import { cn } from '@/lib/utils'

export function Logo({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation()
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="size-8 shrink-0" aria-hidden>
        <rect width="32" height="32" rx="8" fill="oklch(0.55 0.17 270)" />
        <path
          d="M6 21c4-8 16-8 20 0"
          fill="none"
          stroke="white"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
        <path
          d="M9 21v-4M16 21v-7M23 21v-4"
          stroke="white"
          strokeWidth="2.5"
          strokeLinecap="round"
        />
      </svg>
      {!compact && (
        <div className="leading-tight">
          <p className="font-semibold tracking-tight text-sidebar-primary">{t('app.name')}</p>
          <p className="text-[11px] text-sidebar-foreground/70">{t('app.tagline')}</p>
        </div>
      )}
    </div>
  )
}

function Item({
  item,
  badge,
  onNavigate,
}: {
  item: NavItem
  badge?: number
  onNavigate?: () => void
}) {
  const { t } = useTranslation()
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-sidebar-ring',
          isActive
            ? 'bg-sidebar-accent text-sidebar-accent-foreground shadow-[inset_3px_0_0_var(--sidebar-ring)]'
            : 'text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground',
        )
      }
    >
      <Icon className="size-4.5 shrink-0" aria-hidden />
      <span className="flex-1 truncate">{t(item.labelKey)}</span>
      {badge ? (
        <span className="grid h-5 min-w-5 place-items-center rounded-full bg-danger px-1.5 text-[11px] font-semibold text-white">
          {badge}
          <span className="sr-only"> new high-priority recommendations</span>
        </span>
      ) : null}
    </NavLink>
  )
}

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useTranslation()
  const recommendations = useRecommendations()
  const newHigh =
    recommendations.data?.data.filter((r) => r.status === 'NEW' && r.priority === 'HIGH').length ??
    0
  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      <div className="px-4 py-5">
        <Logo />
      </div>
      <nav aria-label={t('nav.main')} className="flex flex-1 flex-col gap-1 overflow-y-auto px-3">
        {MAIN_NAV.map((item) => (
          <Item
            key={item.to}
            item={item}
            onNavigate={onNavigate}
            badge={item.to === '/recommendations' ? newHigh : undefined}
          />
        ))}
      </nav>
      <div className="flex flex-col gap-1 border-t border-sidebar-border px-3 py-3">
        {FOOTER_NAV.map((item) => (
          <Item key={item.to} item={item} onNavigate={onNavigate} />
        ))}
      </div>
      <p className="px-5 pb-4 text-[11px] leading-snug text-sidebar-foreground/60">
        Prototype · synthetic demo data · not official statistics
      </p>
    </div>
  )
}

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-sidebar-border lg:block">
      <SidebarNav />
    </aside>
  )
}
