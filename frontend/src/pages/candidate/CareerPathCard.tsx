// One ranked career path for a candidate: demand, trend, estimated openings, why, skills, courses.
import {
  Award,
  BatteryCharging,
  Briefcase,
  GraduationCap,
  Lightbulb,
  Sun,
  Wrench,
  Zap,
} from 'lucide-react'
import type { ReactNode } from 'react'

import { Pill, TrendBadge } from '@/components/badges'
import type { CareerPath, SectorCode } from '@/lib/api/types'
import { fmtInt, fmtScore } from '@/lib/format'
import { cn } from '@/lib/utils'

const SECTOR_META: Record<SectorCode, { label: string; icon: ReactNode }> = {
  ELECTRICAL: { label: 'Electrical', icon: <Zap aria-hidden /> },
  EV: { label: 'EV', icon: <BatteryCharging aria-hidden /> },
  SOLAR_PV: { label: 'Solar PV', icon: <Sun aria-hidden /> },
}

export function SectorPill({ sector }: { sector: SectorCode }) {
  const meta = SECTOR_META[sector]
  return (
    <Pill icon={meta?.icon} title="Sector">
      {meta?.label ?? sector}
    </Pill>
  )
}

function SubHeading({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <h4 className="flex items-center gap-1.5 text-xs font-semibold tracking-wide text-muted-foreground uppercase [&_svg]:size-3.5">
      {icon}
      {children}
    </h4>
  )
}

export function CareerPathCard({
  path,
  rank,
  best,
}: {
  path: CareerPath
  rank: number
  best: boolean
}) {
  const width = Math.max(0, Math.min(100, path.demand_score))
  const titleId = `career-path-${path.role.code}`
  return (
    <article
      aria-labelledby={titleId}
      className={cn(
        'animate-in-up rounded-xl border bg-card p-5 shadow-xs',
        best && 'border-primary/50 ring-1 ring-primary/20',
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 gap-3">
          <span
            className={cn(
              'tabular grid size-8 shrink-0 place-items-center rounded-full text-sm font-semibold',
              best ? 'bg-primary text-primary-foreground' : 'bg-accent text-primary',
            )}
          >
            <span className="sr-only">Rank </span>
            {rank}
          </span>
          <div className="min-w-0 space-y-2">
            {best && (
              <Pill tone="primary" icon={<Award aria-hidden />}>
                Best match for demand
              </Pill>
            )}
            <h3 id={titleId} className="text-lg leading-tight font-semibold">
              {path.role.title}
            </h3>
            <div className="flex flex-wrap items-center gap-2">
              <SectorPill sector={path.role.sector} />
              <TrendBadge trend={path.trend} />
            </div>
          </div>
        </div>

        <div className="w-40 shrink-0 sm:text-right">
          <p className="text-xs font-medium text-muted-foreground">Demand score</p>
          <p className="tabular text-2xl font-semibold tracking-tight">
            {fmtScore(path.demand_score)}
            <span className="text-sm font-normal text-muted-foreground"> / 100</span>
          </p>
          <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
            <div className="h-full rounded-full bg-primary" style={{ width: `${width}%` }} />
          </div>
        </div>
      </div>

      <p className="mt-4 flex items-start gap-2 text-sm">
        <Briefcase className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
        <span>
          <span className="font-medium">
            ~{fmtInt(Math.round(path.estimated_openings))} estimated openings a year
          </span>{' '}
          <span className="text-muted-foreground">(model estimate)</span>
        </span>
      </p>

      <p className="mt-3 flex items-start gap-2 rounded-lg bg-muted/60 px-3.5 py-2.5 text-sm">
        <Lightbulb className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
        <span>
          <span className="font-medium">Why: </span>
          <span className="text-muted-foreground">{path.why}</span>
        </span>
      </p>

      <div className="mt-4 grid gap-5 md:grid-cols-2">
        <div>
          <SubHeading icon={<Wrench aria-hidden />}>Skills to learn</SubHeading>
          {path.skills_to_learn.length > 0 ? (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {path.skills_to_learn.map((skill) => (
                <li
                  key={skill.code}
                  className="rounded-full border bg-background px-2.5 py-0.5 text-xs font-medium"
                >
                  {skill.name}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">
              No skill list for this role in the demo data yet.
            </p>
          )}
        </div>
        <div>
          <SubHeading icon={<GraduationCap aria-hidden />}>Typical courses</SubHeading>
          {path.typical_courses.length > 0 ? (
            <ul className="mt-2 space-y-1.5">
              {path.typical_courses.map((course) => (
                <li key={`${course.name}-${course.institute}`} className="text-sm leading-snug">
                  <span className="font-medium">{course.name}</span>
                  <span className="text-muted-foreground">
                    {' '}
                    · {course.institute} · {course.duration}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">
              No demo course trains for this role here yet.
            </p>
          )}
        </div>
      </div>
    </article>
  )
}
