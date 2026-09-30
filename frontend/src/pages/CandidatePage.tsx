// Career Guidance (/candidate): for a young person or ITI student. Career paths in a district,
// ranked by demand, with skills and courses, plus a rule-based assistant that restates them.
import { FlaskConical, Languages, MapPin, School, UserRound } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { useFilters } from '@/app/filters'
import { DataSourceBadge, SyntheticBadge } from '@/components/badges'
import { Callout } from '@/components/cards'
import { Panel, PageHeader } from '@/components/headers'
import { EmptyState, QueryState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useCareerPaths } from '@/lib/api/queries'
import type { CareerPath, SectorCode } from '@/lib/api/types'
import { DISTRICTS } from '@/lib/demo/catalog'
import { districtName } from '@/lib/format'
import { cn } from '@/lib/utils'
import { CareerAssistant } from '@/pages/candidate/CareerAssistant'
import { CareerPathCard } from '@/pages/candidate/CareerPathCard'

type Interest = SectorCode | 'ALL'

const INTERESTS: { value: Interest; label: string }[] = [
  { value: 'ALL', label: 'All' },
  { value: 'ELECTRICAL', label: 'Electrical' },
  { value: 'EV', label: 'EV' },
  { value: 'SOLAR_PV', label: 'Solar PV' },
]

const DEFAULT_DISTRICT = 'MH-NASHIK'

function byInterest(paths: CareerPath[], interest: Interest): CareerPath[] {
  return interest === 'ALL' ? paths : paths.filter((p) => p.role.sector === interest)
}

function ProfileRow({
  icon,
  label,
  children,
}: {
  icon: ReactNode
  label: string
  children: ReactNode
}) {
  return (
    <div className="flex gap-3">
      <dt className="flex w-28 shrink-0 items-center gap-1.5 text-muted-foreground [&_svg]:size-3.5">
        {icon}
        {label}
      </dt>
      <dd className="min-w-0 font-medium">{children}</dd>
    </div>
  )
}

function DemoProfile() {
  return (
    <Panel
      title="Your profile (demo)"
      actions={<SyntheticBadge />}
      className="h-full"
      bodyClassName="space-y-3"
    >
      <dl className="space-y-2.5 text-sm">
        <ProfileRow icon={<UserRound aria-hidden />} label="Learner">
          Demo learner DC-0421{' '}
          <span className="font-normal text-muted-foreground">(pseudonymous)</span>
        </ProfileRow>
        <ProfileRow icon={<Languages aria-hidden />} label="Languages">
          Marathi, Hindi, English
        </ProfileRow>
        <ProfileRow icon={<School aria-hidden />} label="Education">
          Class 10 passed · ITI Electrician, 1st year
        </ProfileRow>
      </dl>
      <p className="text-xs text-muted-foreground">
        A made-up demo profile. No personal details are collected on this page.
      </p>
    </Panel>
  )
}

export default function CandidatePage() {
  const filters = useFilters()
  const globalDistrict = DISTRICTS.some((d) => d.code === filters.district)
    ? filters.district
    : null
  // The page follows the global district filter until the candidate picks a district here; a later
  // change of the global filter takes over again.
  const [choice, setChoice] = useState<{ code: string; global: string | null } | null>(null)
  const district =
    choice && choice.global === globalDistrict ? choice.code : (globalDistrict ?? DEFAULT_DISTRICT)
  const districtLabel = DISTRICTS.find((d) => d.code === district)?.name ?? districtName(district)
  const [interest, setInterest] = useState<Interest>(filters.sector)

  const paths = useCareerPaths(district)
  const all = paths.data?.data ?? []
  const interestLabel = INTERESTS.find((i) => i.value === interest)?.label ?? 'All'

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="For students and job seekers"
        title="Career Guidance"
        description="See which Electrical, EV and Solar PV jobs are in demand in your district, which skills to learn and where you can train."
        badges={<SyntheticBadge />}
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px] 2xl:grid-cols-[minmax(0,1fr)_420px]">
        <section
          aria-label="Choose district and interest"
          className="animate-in-up flex flex-wrap items-end gap-x-8 gap-y-4 rounded-xl border bg-card p-5 shadow-xs"
        >
          <div className="space-y-2">
            <Label htmlFor="candidate-district" className="flex items-center gap-1.5">
              <MapPin className="size-3.5 text-muted-foreground" aria-hidden /> Your district
            </Label>
            <Select
              value={district}
              onValueChange={(code) => setChoice({ code, global: globalDistrict })}
            >
              <SelectTrigger id="candidate-district" className="h-9 w-56 bg-card">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DISTRICTS.map((d) => (
                  <SelectItem key={d.code} value={d.code}>
                    {d.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <p id="candidate-interest" className="text-sm leading-none font-medium">
              I am interested in
            </p>
            <div role="group" aria-labelledby="candidate-interest" className="flex flex-wrap gap-2">
              {INTERESTS.map((option) => {
                const active = option.value === interest
                const count = paths.isSuccess ? byInterest(all, option.value).length : null
                return (
                  <button
                    key={option.value}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setInterest(option.value)}
                    className={cn(
                      'inline-flex h-9 items-center gap-1.5 rounded-full border px-4 text-sm font-medium transition-colors focus-visible:outline-2',
                      active
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'bg-card text-foreground hover:border-primary/40 hover:bg-accent',
                    )}
                  >
                    {option.label}
                    {count !== null && (
                      <span
                        className={cn(
                          'tabular text-xs',
                          active ? 'text-primary-foreground/80' : 'text-muted-foreground',
                        )}
                      >
                        ({count})
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        </section>

        <DemoProfile />
      </div>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_360px] 2xl:grid-cols-[minmax(0,1fr)_420px]">
        <Panel
          title={`Career paths in ${districtLabel}`}
          description="Ranked from the highest to the lowest demand score (out of 100). Openings are model estimates, not official figures."
          actions={<DataSourceBadge source={paths.data?.source} note={paths.data?.note} />}
        >
          <QueryState
            query={paths}
            loadingRows={5}
            isEmpty={(res) => byInterest(res.data, interest).length === 0}
            empty={
              all.length === 0 ? (
                <EmptyState
                  title={`No demand data for ${districtLabel} yet`}
                  description="Try another district."
                />
              ) : (
                <EmptyState
                  title={`No ${interestLabel} career paths in ${districtLabel}`}
                  description="Try another interest or another district."
                  action={
                    <Button variant="outline" size="sm" onClick={() => setInterest('ALL')}>
                      Show all interests
                    </Button>
                  }
                />
              )
            }
          >
            {(res) => {
              const shown = byInterest(res.data, interest)
              const growing = shown.filter(
                (p) => p.trend === 'GROWING' || p.trend === 'EMERGING',
              ).length
              return (
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    {growing > 0
                      ? `Good news: ${growing} of these ${shown.length} roles ${growing === 1 ? 'is' : 'are'} growing in ${districtLabel}. `
                      : `${shown.length} role${shown.length === 1 ? '' : 's'} shown for ${districtLabel}. `}
                    Pick one that matches what you enjoy, then look at the skills and courses that
                    lead to it.
                  </p>
                  <ol className="space-y-4">
                    {shown.map((path, index) => (
                      <li key={path.role.code}>
                        <CareerPathCard path={path} rank={index + 1} best={index === 0} />
                      </li>
                    ))}
                  </ol>
                </div>
              )
            }}
          </QueryState>
        </Panel>

        <div className="space-y-4 lg:sticky lg:top-20">
          <CareerAssistant
            key={district}
            paths={all}
            districtLabel={districtLabel}
            ready={paths.isSuccess && all.length > 0}
            loading={paths.isPending}
          />
          <Callout
            tone="demo"
            icon={<FlaskConical aria-hidden />}
            title="Practice data, not real job numbers"
          >
            Every job, score and course here comes from a synthetic demo world. Use it to explore
            how career guidance could work, and talk to your ITI or a career counsellor before you
            choose a course.
          </Callout>
        </div>
      </div>
    </div>
  )
}
