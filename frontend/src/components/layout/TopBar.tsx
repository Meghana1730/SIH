import { Bell, Globe, LogOut, Menu, UserRound } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { SECTORS, useFilters } from '@/app/filters'
import { ROLE_LABELS, useSession } from '@/app/session'
import { Pill } from '@/components/badges'
import { SidebarNav } from '@/components/layout/Sidebar'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'
import { LANGUAGES } from '@/i18n'
import { useDistricts, useQuarters } from '@/lib/api/queries'
import type { Notification } from '@/lib/api/types'
import { NOTIFICATIONS } from '@/lib/demo/people'
import { useDemoState } from '@/lib/demo/store'
import { cn } from '@/lib/utils'

function Selector({
  id,
  label,
  value,
  onChange,
  options,
  className,
}: {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
  className?: string
}) {
  return (
    <div className={cn('flex flex-col', className)}>
      <span id={id} className="sr-only">
        {label}
      </span>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger aria-labelledby={id} size="sm" className="h-8 min-w-0 bg-card text-xs">
          <span className="text-muted-foreground">{label}:</span>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}

const TONE_DOT: Record<Notification['tone'], string> = {
  danger: 'bg-danger',
  warning: 'bg-warning',
  info: 'bg-info',
  success: 'bg-success',
}

function Notifications() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const demo = useDemoState()
  const items: Notification[] = [
    ...(demo.evExpansionSimulated
      ? [
          {
            id: 'sim',
            title: 'Simulated: Nashik EV expansion',
            body: 'EV battery-pack assembly unit (simulated event): about 180 EV Service Technician jobs expected in 2026Q4-2027Q3.',
            at: 'now',
            href: '/districts/MH-NASHIK',
            tone: 'danger' as const,
          },
        ]
      : []),
    ...demo.activity.slice(0, 3).map((a) => ({
      id: a.id,
      title:
        a.kind === 'PLEDGE'
          ? 'Apprenticeship pledge'
          : a.kind === 'VALIDATION'
            ? 'Employer validation'
            : 'Employer demand',
      body: a.text,
      at: new Date(a.at).toLocaleDateString('en-IN'),
      href: '/employer',
      tone: 'success' as const,
    })),
    ...NOTIFICATIONS,
  ]
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative"
          aria-label={`${t('topbar.notifications')} (${items.length})`}
        >
          <Bell aria-hidden />
          <span
            className="absolute top-1 right-1 grid h-4 min-w-4 place-items-center rounded-full bg-danger px-1 text-[10px] font-semibold text-white"
            aria-hidden
          >
            {items.length}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-96">
        <DropdownMenuLabel className="flex items-center justify-between">
          {t('topbar.notifications')}
          <Pill tone="demo" className="h-5 text-[10px]">
            Demo
          </Pill>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {items.map((n) => (
          <DropdownMenuItem
            key={n.id}
            className="items-start gap-3 py-2.5"
            onSelect={() => n.href && navigate(n.href)}
          >
            <span
              className={cn('mt-1.5 size-2 shrink-0 rounded-full', TONE_DOT[n.tone])}
              aria-hidden
            />
            <span className="min-w-0 space-y-0.5">
              <span className="block text-sm font-medium">{n.title}</span>
              <span className="block text-xs whitespace-normal text-muted-foreground">
                {n.body}
              </span>
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function Profile() {
  const { t, i18n } = useTranslation()
  const { user, mode, logout } = useSession()
  const navigate = useNavigate()
  if (!user) return null
  const initials = user.display_name
    .split(/\s+/)
    .filter((w) => /^[A-Z]/.test(w))
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex items-center gap-2 rounded-lg px-1.5 py-1 text-left hover:bg-muted focus-visible:outline-2"
          aria-label={`${t('topbar.profile')}: ${user.display_name}`}
        >
          <Avatar className="size-8">
            <AvatarFallback className="bg-primary text-xs font-semibold text-primary-foreground">
              {initials || <UserRound className="size-4" />}
            </AvatarFallback>
          </Avatar>
          <span className="hidden leading-tight xl:block">
            <span className="block max-w-40 truncate text-sm font-medium">{user.display_name}</span>
            <span className="block text-[11px] text-muted-foreground">
              {ROLE_LABELS[user.role]}
            </span>
          </span>
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel>
          <p className="truncate font-medium">{user.display_name}</p>
          <p className="truncate text-xs font-normal text-muted-foreground">{user.email}</p>
          <p className="mt-1.5">
            {mode === 'api' ? (
              <Pill tone="info" className="h-5 text-[10px]">
                Signed in to the API
              </Pill>
            ) : (
              <Pill tone="demo" className="h-5 text-[10px]">
                Offline demo mode
              </Pill>
            )}
          </p>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuLabel className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
          <Globe className="size-3.5" aria-hidden /> {t('topbar.language')}
        </DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={i18n.language}
          onValueChange={(value) => void i18n.changeLanguage(value)}
        >
          {LANGUAGES.map((language) => (
            <DropdownMenuRadioItem key={language.code} value={language.code}>
              {language.label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/settings">{t('nav.settings')}</Link>
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() => {
            logout()
            navigate('/login')
          }}
        >
          <LogOut aria-hidden /> {t('topbar.signOut')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function TopBar({ title }: { title: string }) {
  const { t } = useTranslation()
  const filters = useFilters()
  const districts = useDistricts()
  const quarters = useQuarters()
  const [menuOpen, setMenuOpen] = useState(false)
  const latest = quarters.data?.[quarters.data.length - 1]

  return (
    <header className="sticky top-0 z-20 border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80">
      <div className="flex h-16 items-center gap-3 px-4 lg:px-8">
        <Button
          variant="ghost"
          size="icon"
          className="lg:hidden"
          aria-label={t('topbar.openMenu')}
          onClick={() => setMenuOpen(true)}
        >
          <Menu aria-hidden />
        </Button>
        <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
          <SheetContent side="left" className="w-64 border-0 p-0" showCloseButton={false}>
            <SheetTitle className="sr-only">{t('nav.main')}</SheetTitle>
            <SidebarNav onNavigate={() => setMenuOpen(false)} />
          </SheetContent>
        </Sheet>
        <p className="min-w-0 flex-1 truncate text-base font-semibold text-foreground" aria-hidden>
          {title}
        </p>
        <div className="hidden items-center gap-2 md:flex">
          <Selector
            id="global-sector"
            label={t('topbar.sector')}
            value={filters.sector}
            onChange={(value) => filters.setSector(value as typeof filters.sector)}
            options={[
              { value: 'ALL', label: t('topbar.allSectors') },
              ...SECTORS.map((s) => ({ value: s.code, label: s.label })),
            ]}
          />
          <Selector
            id="global-district"
            label={t('topbar.district')}
            value={filters.district}
            onChange={filters.setDistrict}
            options={[
              { value: 'ALL', label: t('topbar.allDistricts') },
              ...(districts.data?.data ?? []).map((d) => ({ value: d.code, label: d.name })),
            ]}
          />
          <Selector
            id="global-quarter"
            label={t('topbar.quarter')}
            value={filters.quarter ?? 'LATEST'}
            onChange={(value) => filters.setQuarter(value === 'LATEST' ? null : value)}
            options={[
              { value: 'LATEST', label: `${t('topbar.latest')}${latest ? ` (${latest})` : ''}` },
              ...[...(quarters.data ?? [])].reverse().map((q) => ({ value: q, label: q })),
            ]}
          />
        </div>
        <Notifications />
        <Profile />
      </div>
    </header>
  )
}
