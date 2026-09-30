// The district plan as a printable document: header, summary, key numbers, priorities, actions,
// evidence links and a disclaimer. Seats pledged and employer validations come from the demo store.
import {
  ArrowRight,
  BadgeCheck,
  BookPlus,
  CircleCheck,
  Download,
  FileSearch,
  FlaskConical,
  Handshake,
  Send,
  Target,
  Wrench,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { DataSourceBadge, Pill, StatusBadge, SyntheticBadge } from '@/components/badges'
import { Callout, MetricCard } from '@/components/cards'
import { ConfirmDialog } from '@/components/overlays'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import type { DataSource } from '@/lib/api/client'
import { errorMessage, useSubmitPlan } from '@/lib/api/queries'
import type { DistrictPlan } from '@/lib/api/types'
import { fmtDate } from '@/lib/format'
import { PlanActionsTable } from '@/pages/plans/PlanActionsTable'

const SEATS_LABEL = 'Apprenticeship seats pledged'
const VALIDATIONS_LABEL = 'Employer validations received'

const COMMITMENT_ICON: Record<string, ReactNode> = {
  'Courses re-tooled': <Wrench aria-hidden />,
  'New short courses': <BookPlus aria-hidden />,
  [SEATS_LABEL]: <Handshake aria-hidden />,
  [VALIDATIONS_LABEL]: <BadgeCheck aria-hidden />,
}

const COMMITMENT_HINT: Record<string, string> = {
  [SEATS_LABEL]:
    'Seats employers pledged for courses in this district in the Employer portal (demo).',
  [VALIDATIONS_LABEL]: 'Employer validations agreeing with a recommendation (demo).',
}

/** Evidence pages behind the Nashik plan. */
const NASHIK_EVIDENCE = [
  {
    to: '/districts/MH-NASHIK',
    label: 'Nashik district intelligence',
    detail: 'Demand, trained supply and shortage status for each role, behind the EV priority.',
  },
  {
    to: '/skills/ev-diagnostics',
    label: 'EV Diagnostics skill trend',
    detail: 'How often the skill appears in job ads and how its demand is changing.',
  },
  {
    to: '/courses/nsk-iti-a-electrician',
    label: 'Course health: Electrician (demo syllabus), Example ITI A',
    detail: 'Curriculum coverage and missing skills of the course this plan re-tools.',
  },
]

function DocSection({
  id,
  number,
  title,
  description,
  children,
}: {
  id: string
  number: number
  title: string
  description?: ReactNode
  children: ReactNode
}) {
  return (
    <section aria-labelledby={id} className="space-y-3">
      <div>
        <h3 id={id} className="flex items-baseline gap-2 text-base font-semibold">
          <span className="tabular text-sm text-primary">{number}.</span>
          {title}
        </h3>
        {description && <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>}
      </div>
      {children}
    </section>
  )
}

function Meta({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="truncate text-sm font-medium">{children}</dd>
    </div>
  )
}

export function PlanDocument({
  plan,
  source,
  note,
}: {
  plan: DistrictPlan
  source: DataSource
  note?: string
}) {
  const submit = useSubmitPlan()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const seats = Number(plan.commitments.find((c) => c.label === SEATS_LABEL)?.value ?? 0)
  const isDraft = plan.status === 'DRAFT'
  const evidence =
    plan.district.code === 'MH-NASHIK'
      ? NASHIK_EVIDENCE
      : [
          {
            to: `/districts/${plan.district.code}`,
            label: `${plan.district.name} district intelligence`,
            detail: 'Demand, trained supply and shortage status for each role.',
          },
        ]

  function confirmSubmit() {
    submit.mutate(undefined, {
      onSuccess: () => {
        setConfirmOpen(false)
        toast.success('Plan submitted for approval', {
          description:
            source === 'demo'
              ? 'Status is now In review. Demo only: saved in this browser.'
              : 'Status is now In review.',
        })
      },
      onError: (error) => toast.error(errorMessage(error)),
    })
  }

  return (
    <article
      data-print-area
      aria-labelledby="plan-title"
      className="animate-in-up rounded-xl border bg-card shadow-xs"
    >
      {/* Document header (a div, not <header>: the print stylesheet hides <header> elements). */}
      <div className="flex flex-wrap items-start justify-between gap-4 border-b px-6 py-5 lg:px-8">
        <div className="min-w-0 flex-1 space-y-3">
          <p className="text-xs font-semibold tracking-wider text-primary uppercase">
            District skill plan
          </p>
          <h2 id="plan-title" className="text-xl font-semibold tracking-tight">
            {plan.title}
          </h2>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={plan.status} />
            <DataSourceBadge source={source} note={note} />
            <SyntheticBadge />
          </div>
          <dl className="grid max-w-3xl grid-cols-2 gap-x-6 gap-y-3 pt-1 sm:grid-cols-4">
            <Meta label="District">{plan.district.name}</Meta>
            <Meta label="Period">{plan.period}</Meta>
            <Meta label="Prepared by">{plan.prepared_by}</Meta>
            <Meta label="Last updated">{fmtDate(plan.updated_at)}</Meta>
          </dl>
        </div>

        <div data-print-hide className="flex flex-col items-end gap-1.5">
          <div className="flex flex-wrap justify-end gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  className="h-9"
                  onClick={() => window.print()}
                  aria-describedby="plan-pdf-note"
                >
                  <Download aria-hidden /> Download PDF
                </Button>
              </TooltipTrigger>
              <TooltipContent>PDF export uses your browser&apos;s Save as PDF</TooltipContent>
            </Tooltip>
            <Button className="h-9" disabled={!isDraft} onClick={() => setConfirmOpen(true)}>
              {isDraft ? (
                <>
                  <Send aria-hidden /> Submit for approval
                </>
              ) : (
                <>
                  <CircleCheck aria-hidden /> Submitted for approval
                </>
              )}
            </Button>
          </div>
          <p id="plan-pdf-note" className="text-xs text-muted-foreground">
            PDF export uses your browser&apos;s Save as PDF.
          </p>
        </div>
      </div>

      <div className="space-y-8 px-6 py-6 lg:px-8">
        {plan.status === 'IN_REVIEW' && (
          <div data-print-hide>
            <Callout
              tone="success"
              icon={<CircleCheck aria-hidden />}
              title="Submitted for approval"
            >
              This plan is in review. Action progress can still be updated below.
              {source === 'demo' ? ' In this demo the status is saved in this browser only.' : ''}
            </Callout>
          </div>
        )}

        <DocSection id="plan-summary" number={1} title="Summary">
          <p className="max-w-4xl text-sm leading-relaxed text-foreground/90">{plan.summary}</p>
        </DocSection>

        <DocSection
          id="plan-numbers"
          number={2}
          title="Key numbers"
          description="Commitments in this plan. Seats pledged and employer validations update when employers act in the Employer portal."
        >
          <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">
            {plan.commitments.map((c) => {
              const isSeats = c.label === SEATS_LABEL
              const live = isSeats || c.label === VALIDATIONS_LABEL
              return (
                <div
                  key={c.label}
                  className={
                    isSeats
                      ? 'rounded-xl ring-2 ring-primary/60 ring-offset-2 ring-offset-card'
                      : undefined
                  }
                >
                  <MetricCard
                    label={c.label}
                    value={c.value}
                    icon={COMMITMENT_ICON[c.label] ?? <Target aria-hidden />}
                    tone={isSeats ? 'success' : live ? 'info' : 'primary'}
                    hint={COMMITMENT_HINT[c.label]}
                    footer={
                      live ? (
                        <Pill tone={isSeats ? 'primary' : 'neutral'} className="self-start">
                          Updates from employer actions
                        </Pill>
                      ) : undefined
                    }
                  />
                </div>
              )
            })}
          </div>
          {seats === 0 && (
            <div data-print-hide>
              <Callout
                tone="info"
                icon={<Handshake aria-hidden />}
                title="No apprenticeship seats pledged yet"
              >
                Employers can pledge from the{' '}
                <Link
                  to="/employer"
                  className="font-medium text-primary underline-offset-2 hover:underline focus-visible:outline-2"
                >
                  Employer portal
                </Link>
                .
              </Callout>
            </div>
          )}
        </DocSection>

        <DocSection id="plan-priorities" number={3} title="Priorities">
          <ol className="grid gap-4 md:grid-cols-3">
            {plan.priorities.map((priority, index) => (
              <li key={priority.title} className="flex flex-col rounded-xl border bg-card p-4">
                <p className="text-xs font-semibold tracking-wide text-primary uppercase">
                  Priority {index + 1}
                </p>
                <p className="mt-1 font-semibold">{priority.title}</p>
                <p className="mt-1.5 flex-1 text-sm text-muted-foreground">{priority.detail}</p>
                <p className="mt-3 flex items-start gap-1.5 rounded-md bg-accent px-3 py-2 text-xs font-medium text-accent-foreground">
                  <Target className="mt-px size-3.5 shrink-0" aria-hidden />
                  <span>
                    <span className="sr-only">Measure: </span>
                    {priority.metric.replace('->', '→')}
                  </span>
                </p>
              </li>
            ))}
          </ol>
        </DocSection>

        <DocSection
          id="plan-actions"
          number={4}
          title="Actions"
          description="Change an action's status as work progresses."
        >
          <PlanActionsTable actions={plan.actions} />
        </DocSection>

        <DocSection
          id="plan-evidence"
          number={5}
          title="Evidence behind this plan"
          description="Open the analysis each part of the plan is based on."
        >
          <ul className="space-y-2">
            {evidence.map((item) => (
              <li key={item.to} className="flex items-start gap-2.5 text-sm">
                <FileSearch className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
                <span>
                  <Link
                    to={item.to}
                    className="inline-flex items-center gap-1 rounded font-medium text-primary hover:underline focus-visible:outline-2"
                  >
                    {item.label}
                    <ArrowRight className="size-3.5 print:hidden" aria-hidden />
                  </Link>
                  <span className="text-muted-foreground">: {item.detail}</span>
                </span>
              </li>
            ))}
          </ul>
        </DocSection>
      </div>

      <footer className="flex items-start gap-2 rounded-b-xl border-t bg-muted/40 px-6 py-4 text-xs text-muted-foreground lg:px-8">
        <FlaskConical className="mt-px size-3.5 shrink-0 text-demo" aria-hidden />
        Draft generated from synthetic demo data for demonstration; not an official government plan.
      </footer>

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Submit this plan for approval?"
        description={
          <>
            The draft moves to In review.
            {source === 'demo'
              ? ' In this demo the change is saved in this browser only; nothing is sent to any office.'
              : ''}
          </>
        }
        confirmLabel="Submit for approval"
        pending={submit.isPending}
        onConfirm={confirmSubmit}
      />
    </article>
  )
}
