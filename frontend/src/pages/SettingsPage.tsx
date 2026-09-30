// Settings: interface language, global filters, data & privacy notes and the current account.
import {
  Database,
  EyeOff,
  FlaskConical,
  Globe,
  HardDrive,
  LogOut,
  RotateCcw,
  SlidersHorizontal,
  UserRound,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { SECTORS, useFilters } from '@/app/filters'
import { ROLE_LABELS, useSession } from '@/app/session'
import { Pill } from '@/components/badges'
import { PageHeader, Panel } from '@/components/headers'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { LANGUAGES } from '@/i18n'
import { DISTRICTS } from '@/lib/demo/catalog'
import { districtName } from '@/lib/format'

const LANGUAGE_NAMES: Record<string, string> = { en: 'English', hi: 'Hindi', mr: 'Marathi' }

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="flex min-w-0 flex-wrap items-center justify-end gap-2 text-sm font-medium">
        {children}
      </dd>
    </div>
  )
}

function Point({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-accent text-primary [&_svg]:size-4">
        {icon}
      </span>
      <div className="min-w-0">
        <p className="text-sm font-medium">{title}</p>
        <p className="text-sm text-muted-foreground">{children}</p>
      </div>
    </li>
  )
}

export default function SettingsPage() {
  const { t, i18n } = useTranslation()
  const filters = useFilters()
  const session = useSession()
  const [announcement, setAnnouncement] = useState('')

  const current = (i18n.resolvedLanguage ?? i18n.language ?? 'en').slice(0, 2)

  function changeLanguage(code: string) {
    void i18n.changeLanguage(code)
    setAnnouncement(`Language changed to ${LANGUAGE_NAMES[code] ?? code}.`)
  }

  const sectorLabel =
    filters.sector === 'ALL'
      ? t('topbar.allSectors')
      : (SECTORS.find((s) => s.code === filters.sector)?.label ?? filters.sector)
  const districtLabel =
    filters.district === 'ALL'
      ? t('topbar.allDistricts')
      : (DISTRICTS.find((d) => d.code === filters.district)?.name ?? districtName(filters.district))
  const isDefault =
    filters.sector === 'ALL' && filters.district === 'ALL' && filters.quarter === null

  function resetFilters() {
    filters.setSector('ALL')
    filters.setDistrict('ALL')
    filters.setQuarter(null)
    setAnnouncement('Filters reset to all sectors, all districts and the latest quarter.')
    toast.success('Filters reset')
  }

  const user = session.user
  const isApi = session.mode === 'api'

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('pages.settings')}
        description="Interface language, the filters applied across pages, and how this prototype handles data."
      />
      <p className="sr-only" role="status" aria-live="polite">
        {announcement}
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* ------------------------------------------------------------ language */}
        <Panel
          className="animate-in-up"
          title={
            <span className="inline-flex items-center gap-2">
              <Globe className="size-4 text-primary" aria-hidden /> {t('topbar.language')}
            </span>
          }
          description="Navigation, page titles and common labels are translated. Data such as role, skill and course names stays as stored."
        >
          <RadioGroup
            value={current}
            onValueChange={changeLanguage}
            aria-label={t('topbar.language')}
            className="grid gap-3 sm:grid-cols-3"
          >
            {LANGUAGES.map((language) => (
              <Label
                key={language.code}
                htmlFor={`language-${language.code}`}
                className="flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/60 has-[[data-state=checked]]:border-primary has-[[data-state=checked]]:bg-accent"
              >
                <RadioGroupItem id={`language-${language.code}`} value={language.code} />
                <span className="flex flex-col gap-0.5">
                  <span lang={language.code} className="text-sm font-semibold">
                    {language.label}
                  </span>
                  <span className="text-xs font-normal text-muted-foreground">
                    {LANGUAGE_NAMES[language.code]}
                  </span>
                </span>
              </Label>
            ))}
          </RadioGroup>
        </Panel>

        {/* ------------------------------------------------------------ filters */}
        <Panel
          className="animate-in-up"
          title={
            <span className="inline-flex items-center gap-2">
              <SlidersHorizontal className="size-4 text-primary" aria-hidden /> Default filters
            </span>
          }
          description="Set from the top bar, saved in this browser and applied on every page."
          actions={
            <Button variant="outline" size="sm" onClick={resetFilters} disabled={isDefault}>
              <RotateCcw aria-hidden /> Reset filters
            </Button>
          }
        >
          <dl className="divide-y">
            <Field label={t('topbar.sector')}>
              <span>{sectorLabel}</span>
            </Field>
            <Field label={t('topbar.district')}>
              <span>{districtLabel}</span>
            </Field>
            <Field label={t('topbar.quarter')}>
              <span>{filters.quarter ?? `${t('topbar.latest')} (current analytics run)`}</span>
            </Field>
          </dl>
          {isDefault && (
            <p className="mt-3 text-xs text-muted-foreground">
              Showing all sectors and districts for the latest quarter (the defaults).
            </p>
          )}
        </Panel>

        {/* ------------------------------------------------------------ data & privacy */}
        <Panel
          className="animate-in-up"
          title={
            <span className="inline-flex items-center gap-2">
              <FlaskConical className="size-4 text-primary" aria-hidden /> Data &amp; privacy
            </span>
          }
        >
          <ul className="space-y-4">
            <Point icon={<FlaskConical aria-hidden />} title="Synthetic data only">
              Every job posting, survey answer, institute and outcome is generated for the demo.
              Nothing here is a real or official statistic.
            </Point>
            <Point icon={<EyeOff aria-hidden />} title="Candidate data is pseudonymous">
              Demo candidates and trainers are synthetic and identified by pseudonyms (for example
              C-ITI-A-electrician-2024-001). No real personal data is stored.
            </Point>
            <Point icon={<HardDrive aria-hidden />} title="Demo actions stay in this browser">
              Recommendation decisions, employer validations, pledges and plan progress are kept in
              this browser&apos;s storage only. Clear them from{' '}
              <Link to="/admin" className="font-medium text-primary hover:underline">
                Demo Controls
              </Link>
              .
            </Point>
          </ul>
        </Panel>

        {/* ------------------------------------------------------------ account */}
        <Panel
          className="animate-in-up"
          title={
            <span className="inline-flex items-center gap-2">
              <UserRound className="size-4 text-primary" aria-hidden /> Account
            </span>
          }
          actions={
            user ? (
              <Button variant="outline" size="sm" onClick={session.logout}>
                <LogOut aria-hidden /> {t('topbar.signOut')}
              </Button>
            ) : undefined
          }
        >
          <dl className="divide-y">
            <Field label="Name">{user?.display_name ?? '-'}</Field>
            <Field label="Email">
              <span className="font-mono text-xs">{user?.email ?? '-'}</span>
            </Field>
            <Field label="Role">{user ? <Pill>{ROLE_LABELS[user.role]}</Pill> : '-'}</Field>
            <Field label="Mode">
              <Pill
                tone={isApi ? 'info' : 'demo'}
                icon={isApi ? <Database aria-hidden /> : <FlaskConical aria-hidden />}
              >
                {isApi ? 'Signed in to the API' : 'Offline demo'}
              </Pill>
            </Field>
          </dl>
        </Panel>
      </div>
    </div>
  )
}
