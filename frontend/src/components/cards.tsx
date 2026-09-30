// Domain cards: metrics, evidence, skill gaps, course health, recommendations, districts.
import { ArrowRight, Building2, CheckCircle2, FileSearch, Info, MapPin } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import {
  ConfidenceBadge,
  EvidenceKindBadge,
  Pill,
  PriorityBadge,
  StatusBadge,
  TrendBadge,
  type Tone,
} from '@/components/badges'
import type {
  Course,
  DistrictMismatch,
  Recommendation,
  SkillRef,
  TrendStatus,
} from '@/lib/api/types'
import { mismatchTone, type EvidenceLike } from '@/lib/evidence'
import { fmtInt, fmtScore } from '@/lib/format'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------- MetricCard
export function MetricCard({
  label,
  value,
  hint,
  icon,
  tone = 'primary',
  footer,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  icon?: ReactNode
  tone?: 'primary' | 'danger' | 'warning' | 'success' | 'info'
  footer?: ReactNode
}) {
  const iconTone = {
    primary: 'bg-accent text-primary',
    danger: 'bg-danger-soft text-danger',
    warning: 'bg-warning-soft text-warning',
    success: 'bg-success-soft text-success',
    info: 'bg-info-soft text-info',
  }[tone]
  return (
    <div className="animate-in-up flex flex-col gap-3 rounded-xl border bg-card p-5 shadow-xs">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium text-muted-foreground">{label}</p>
        {icon && (
          <span
            className={cn('grid size-9 place-items-center rounded-lg [&_svg]:size-4.5', iconTone)}
          >
            {icon}
          </span>
        )}
      </div>
      <p className="tabular text-3xl font-semibold tracking-tight text-foreground">{value}</p>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      {footer}
    </div>
  )
}

// ---------------------------------------------------------------- EvidenceCard
export function EvidenceCard({
  items,
  title = 'Why this matters',
  emptyText = 'No stored evidence for this item.',
  className,
}: {
  items: EvidenceLike[]
  title?: ReactNode
  emptyText?: string
  className?: string
}) {
  return (
    <section className={cn('rounded-xl border bg-card shadow-xs', className)} aria-label="Evidence">
      <div className="flex items-center gap-2 border-b px-5 py-3.5">
        <FileSearch className="size-4 text-primary" aria-hidden />
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      {items.length === 0 ? (
        <p className="px-5 py-4 text-sm text-muted-foreground">{emptyText}</p>
      ) : (
        <ol className="divide-y">
          {items.map((item, index) => (
            <li key={index} className="flex gap-3 px-5 py-3.5">
              <span className="mt-0.5 grid size-6 shrink-0 place-items-center rounded-full bg-accent text-xs font-semibold text-primary">
                {index + 1}
              </span>
              <div className="min-w-0 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-medium">{item.title}</p>
                  <EvidenceKindBadge kind={item.kind} />
                </div>
                <p className="text-sm text-muted-foreground">{item.detail}</p>
                {item.source && (
                  <p className="text-xs text-muted-foreground/80">Source: {item.source}</p>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

// ---------------------------------------------------------------- SkillGapCard
export function SkillGapCard({
  skill,
  demandScore,
  trend,
  postings,
  taught,
  href,
}: {
  skill: SkillRef
  demandScore: number
  trend: TrendStatus | null
  postings?: number
  taught?: string
  href?: string
}) {
  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <p className="font-medium">{skill.name}</p>
        <TrendBadge trend={trend} />
      </div>
      <div className="mt-3 flex items-end justify-between gap-2">
        <div>
          <p className="tabular text-2xl font-semibold">{fmtScore(demandScore)}</p>
          <p className="text-xs text-muted-foreground">demand score / 100</p>
        </div>
        <div className="text-right text-xs text-muted-foreground">
          {postings !== undefined && <p>{fmtInt(postings)} job-ad mentions</p>}
          {taught && <p className="font-medium text-danger">{taught}</p>}
        </div>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${Math.min(100, demandScore)}%` }}
        />
      </div>
    </>
  )
  const className =
    'block rounded-xl border bg-card p-4 shadow-xs transition-colors hover:border-primary/40 focus-visible:outline-2'
  return href ? (
    <Link to={href} className={className}>
      {body}
    </Link>
  ) : (
    <div className={className}>{body}</div>
  )
}

// ---------------------------------------------------------------- ScoreRing / CourseHealthCard
export function ScoreRing({
  score,
  size = 96,
  label,
}: {
  score: number
  size?: number
  label?: string
}) {
  const tone = score >= 70 ? 'var(--success)' : score >= 50 ? 'var(--warning)' : 'var(--danger)'
  const radius = (size - 10) / 2
  const circumference = 2 * Math.PI * radius
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={`${label ?? 'Score'} ${score} out of 100`}
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--muted)"
          strokeWidth={8}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={tone}
          strokeWidth={8}
          strokeLinecap="round"
          strokeDasharray={`${(score / 100) * circumference} ${circumference}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <span
            className="tabular block text-2xl leading-none font-semibold"
            style={{ fontSize: size / 4 }}
          >
            {score}
          </span>
          <span className="text-[10px] text-muted-foreground">/ 100</span>
        </div>
      </div>
    </div>
  )
}

export function CourseHealthCard({ course }: { course: Course }) {
  return (
    <Link
      to={`/courses/${course.id}`}
      className="animate-in-up flex gap-4 rounded-xl border bg-card p-4 shadow-xs transition-colors hover:border-primary/40 focus-visible:outline-2"
    >
      <ScoreRing score={course.health_score} size={72} label="Course health" />
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={course.health_status} />
        </div>
        <p className="truncate font-medium" title={course.name}>
          {course.name}
        </p>
        <p className="flex items-center gap-1 truncate text-xs text-muted-foreground">
          <Building2 className="size-3.5" aria-hidden /> {course.institute.name}
        </p>
        {course.missing_skills.length > 0 && (
          <p className="truncate text-xs text-danger">
            Missing:{' '}
            {course.missing_skills
              .slice(0, 3)
              .map((m) => m.skill.name)
              .join(', ')}
            {course.missing_skills.length > 3 ? ` +${course.missing_skills.length - 3}` : ''}
          </p>
        )}
      </div>
    </Link>
  )
}

// ---------------------------------------------------------------- RecommendationCard
const ACTION_LABEL: Record<Recommendation['action'], string> = {
  ADD_MODULE: 'Add module',
  UPDATE_MODULE: 'Update module',
  REDUCE_SEATS: 'Reduce seats',
  INCREASE_SEATS: 'Increase seats',
  RETIRE_MODULE: 'Shorten module',
  START_COURSE: 'Start course',
  EMPLOYER_PARTNERSHIP: 'Employer partnership',
}

const ACTION_TONE: Record<Recommendation['action'], Tone> = {
  ADD_MODULE: 'primary',
  UPDATE_MODULE: 'info',
  REDUCE_SEATS: 'warning',
  INCREASE_SEATS: 'success',
  RETIRE_MODULE: 'neutral',
  START_COURSE: 'primary',
  EMPLOYER_PARTNERSHIP: 'info',
}

export function ActionBadge({ action }: { action: Recommendation['action'] }) {
  return (
    <Pill tone={ACTION_TONE[action]} className="uppercase tracking-wide">
      {ACTION_LABEL[action]}
    </Pill>
  )
}

export function RecommendationCard({
  rec,
  onOpen,
  compact = false,
  actions,
}: {
  rec: Recommendation
  onOpen?: () => void
  compact?: boolean
  actions?: ReactNode
}) {
  return (
    <article className="animate-in-up rounded-xl border bg-card p-4 shadow-xs">
      <div className="flex flex-wrap items-center gap-2">
        <ActionBadge action={rec.action} />
        <PriorityBadge priority={rec.priority} score={rec.priority_score} />
        {rec.status !== 'NEW' && <StatusBadge status={rec.status} />}
        {!compact && <ConfidenceBadge confidence={rec.confidence} />}
      </div>
      <h3 className="mt-2.5 font-semibold">{rec.title}</h3>
      <p className="mt-0.5 flex items-center gap-1 text-xs text-muted-foreground">
        <MapPin className="size-3.5" aria-hidden /> {rec.target}
      </p>
      {!compact && <p className="mt-2 text-sm text-muted-foreground">{rec.reason}</p>}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1 text-xs text-muted-foreground">
          <CheckCircle2 className="size-3.5 text-success" aria-hidden />
          {rec.employer_validations} employer validation{rec.employer_validations === 1 ? '' : 's'}{' '}
          · {rec.evidence.length} evidence items
        </p>
        <div className="flex items-center gap-2">
          {actions}
          {onOpen && (
            <button
              type="button"
              onClick={onOpen}
              className="inline-flex items-center gap-1 rounded-md text-sm font-medium text-primary hover:underline focus-visible:outline-2"
            >
              Review <ArrowRight className="size-3.5" aria-hidden />
            </button>
          )}
        </div>
      </div>
    </article>
  )
}

// ---------------------------------------------------------------- DistrictCard
export function DistrictCard({
  summary,
  topShortage,
}: {
  summary: Pick<DistrictMismatch, 'district' | 'mismatch_score' | 'status_counts'>
  topShortage?: { title: string; openings: number; supply: number } | null
}) {
  const tone = mismatchTone(summary.mismatch_score)
  const under = summary.status_counts.UNDER_SUPPLIED ?? 0
  const over = summary.status_counts.OVER_SUPPLIED ?? 0
  return (
    <Link
      to={`/districts/${summary.district.code}`}
      className="animate-in-up group flex flex-col gap-3 rounded-xl border bg-card p-4 shadow-xs transition-colors hover:border-primary/40 focus-visible:outline-2"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-semibold">{summary.district.name}</p>
          <p className="text-xs text-muted-foreground">{summary.district.code}</p>
        </div>
        <Pill tone={tone} title="Demand-weighted mean |ln(supply / openings)|; 0 = balanced">
          Mismatch {fmtScore(summary.mismatch_score)}
        </Pill>
      </div>
      <div className="flex gap-4 text-sm">
        <span>
          <span className="tabular font-semibold text-danger">{under}</span>{' '}
          <span className="text-muted-foreground">shortage roles</span>
        </span>
        <span>
          <span className="tabular font-semibold text-warning">{over}</span>{' '}
          <span className="text-muted-foreground">oversupplied</span>
        </span>
      </div>
      {topShortage && (
        <p className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Largest gap:</span> {topShortage.title}:{' '}
          {fmtInt(topShortage.supply)} trained vs ~{fmtInt(topShortage.openings)} openings / yr
        </p>
      )}
      <span className="mt-auto inline-flex items-center gap-1 text-sm font-medium text-primary">
        Open district{' '}
        <ArrowRight
          className="size-3.5 transition-transform group-hover:translate-x-0.5"
          aria-hidden
        />
      </span>
    </Link>
  )
}

// ---------------------------------------------------------------- small helpers
export function Callout({
  tone = 'info',
  title,
  children,
  icon,
}: {
  tone?: 'info' | 'warning' | 'demo' | 'danger' | 'success'
  title?: ReactNode
  children: ReactNode
  icon?: ReactNode
}) {
  const styles = {
    info: 'border-info/25 bg-info-soft',
    warning: 'border-warning/30 bg-warning-soft',
    demo: 'border-demo/25 bg-demo-soft',
    danger: 'border-danger/25 bg-danger-soft',
    success: 'border-success/25 bg-success-soft',
  }[tone]
  const iconColor = {
    info: 'text-info',
    warning: 'text-warning',
    demo: 'text-demo',
    danger: 'text-danger',
    success: 'text-success',
  }[tone]
  return (
    <div className={cn('flex gap-3 rounded-lg border px-4 py-3 text-sm', styles)}>
      <span className={cn('mt-0.5 shrink-0 [&_svg]:size-4', iconColor)}>
        {icon ?? <Info aria-hidden />}
      </span>
      <div className="min-w-0 space-y-0.5">
        {title && <p className="font-medium text-foreground">{title}</p>}
        <div className="text-muted-foreground">{children}</div>
      </div>
    </div>
  )
}
