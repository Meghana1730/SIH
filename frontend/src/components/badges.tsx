// Status, trend, confidence, priority and data-source badges. Colour is never the only signal:
// every badge carries a text label (and an icon where it helps).
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  CircleAlert,
  CircleCheck,
  Database,
  FlaskConical,
  Sparkles,
  TriangleAlert,
} from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { DataSource } from '@/lib/api/client'
import type { Confidence, Priority, TrendStatus } from '@/lib/api/types'
import { cn } from '@/lib/utils'

export type Tone = 'danger' | 'warning' | 'success' | 'info' | 'neutral' | 'demo' | 'primary'

const TONES: Record<Tone, string> = {
  danger: 'bg-danger-soft text-danger ring-danger/25',
  warning: 'bg-warning-soft text-warning ring-warning/30',
  success: 'bg-success-soft text-success ring-success/25',
  info: 'bg-info-soft text-info ring-info/25',
  neutral: 'bg-muted text-muted-foreground ring-border',
  demo: 'bg-demo-soft text-demo ring-demo/25',
  primary: 'bg-accent text-accent-foreground ring-primary/20',
}

export function Pill({
  tone = 'neutral',
  icon,
  children,
  className,
  title,
}: {
  tone?: Tone
  icon?: ReactNode
  children: ReactNode
  className?: string
  title?: string
}) {
  return (
    <span
      title={title}
      className={cn(
        'inline-flex h-6 shrink-0 items-center gap-1 rounded-md px-2 text-xs font-medium whitespace-nowrap ring-1 ring-inset [&_svg]:size-3.5',
        TONES[tone],
        className,
      )}
    >
      {icon}
      {children}
    </span>
  )
}

const STATUS_TONE: Record<string, Tone> = {
  UNDER_SUPPLIED: 'danger',
  OVER_SUPPLIED: 'warning',
  BALANCED: 'success',
  INSUFFICIENT_DATA: 'neutral',
  AT_RISK: 'danger',
  WATCH: 'warning',
  HEALTHY: 'success',
  NEW: 'info',
  IN_REVIEW: 'warning',
  ACCEPTED: 'success',
  DISMISSED: 'neutral',
  DRAFT: 'neutral',
  APPROVED: 'success',
  PLANNED: 'neutral',
  IN_PROGRESS: 'info',
  DONE: 'success',
}

const STATUS_ICON: Partial<Record<Tone, ReactNode>> = {
  danger: <CircleAlert aria-hidden />,
  warning: <TriangleAlert aria-hidden />,
  success: <CircleCheck aria-hidden />,
}

/** Mismatch status, course health, recommendation or plan status. */
export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const { t } = useTranslation()
  const tone = STATUS_TONE[status] ?? 'neutral'
  const label = t(`status.${status}`, { defaultValue: status.replace(/_/g, ' ').toLowerCase() })
  return (
    <Pill tone={tone} icon={STATUS_ICON[tone]} className={cn('capitalize', className)}>
      {label}
    </Pill>
  )
}

const TREND: Record<TrendStatus, { tone: Tone; icon: ReactNode }> = {
  EMERGING: { tone: 'primary', icon: <Sparkles aria-hidden /> },
  GROWING: { tone: 'success', icon: <ArrowUpRight aria-hidden /> },
  STABLE: { tone: 'neutral', icon: <ArrowRight aria-hidden /> },
  DECLINING: { tone: 'warning', icon: <ArrowDownRight aria-hidden /> },
  INSUFFICIENT_DATA: { tone: 'neutral', icon: null },
}

export function TrendBadge({ trend }: { trend: TrendStatus | null | undefined }) {
  const { t } = useTranslation()
  if (!trend) return <Pill>-</Pill>
  const { tone, icon } = TREND[trend] ?? TREND.STABLE
  return (
    <Pill tone={tone} icon={icon}>
      {t(`status.${trend}`, { defaultValue: trend })}
    </Pill>
  )
}

export function ConfidenceBadge({ confidence }: { confidence: Confidence | null | undefined }) {
  if (!confidence) return null
  const tone: Tone =
    confidence === 'HIGH' ? 'success' : confidence === 'MEDIUM' ? 'info' : 'warning'
  return (
    <Pill tone={tone} title="How much evidence is behind this number">
      {confidence.charAt(0) + confidence.slice(1).toLowerCase()} confidence
    </Pill>
  )
}

export function PriorityBadge({ priority, score }: { priority: Priority; score?: number }) {
  const tone: Tone = priority === 'HIGH' ? 'danger' : priority === 'MEDIUM' ? 'warning' : 'neutral'
  return (
    <Pill tone={tone}>
      {score !== undefined ? `Priority ${score}` : `${priority.toLowerCase()} priority`}
    </Pill>
  )
}

/** Marks a record as synthetic demo-world data. */
export function SyntheticBadge({ className }: { className?: string }) {
  return (
    <Pill
      tone="demo"
      icon={<FlaskConical aria-hidden />}
      className={className}
      title="Generated for the demo; not real labour-market data"
    >
      Synthetic
    </Pill>
  )
}

/**
 * Where a section's data came from.
 * live: the KaushalSetu API (whose data is itself the synthetic demo world, so "synthetic" too)
 * demo: the frontend's deterministic demo fallback
 */
export function DataSourceBadge({
  source,
  note,
  synthetic = true,
}: {
  source: DataSource | undefined
  note?: string
  synthetic?: boolean
}) {
  if (!source) return null
  if (source === 'demo') {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <span tabIndex={0} className="rounded-md focus-visible:outline-2">
            <Pill tone="demo" icon={<FlaskConical aria-hidden />}>
              Demo data
            </Pill>
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">
          {note ?? 'Deterministic demo data from the frontend.'} Not real or official statistics.
        </TooltipContent>
      </Tooltip>
    )
  }
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span tabIndex={0} className="inline-flex gap-1 rounded-md focus-visible:outline-2">
          <Pill tone="info" icon={<Database aria-hidden />}>
            Live API
          </Pill>
          {synthetic && <SyntheticBadge />}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        From the KaushalSetu API.{' '}
        {synthetic
          ? 'The database holds the synthetic demo world, so these are not real or official statistics.'
          : ''}
      </TooltipContent>
    </Tooltip>
  )
}

export function EvidenceKindBadge({
  kind,
}: {
  kind: 'OBSERVED' | 'INFERRED' | 'SYNTHETIC' | 'ASSUMPTION'
}) {
  const tone: Tone =
    kind === 'OBSERVED'
      ? 'success'
      : kind === 'INFERRED'
        ? 'info'
        : kind === 'SYNTHETIC'
          ? 'demo'
          : 'neutral'
  return (
    <Pill tone={tone} className="h-5 text-[11px] uppercase tracking-wide">
      {kind.toLowerCase()}
    </Pill>
  )
}
