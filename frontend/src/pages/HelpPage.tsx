// Help: how the prototype's numbers are made, and a step-by-step demo walkthrough.
import {
  ArrowRight,
  BriefcaseBusiness,
  ClipboardList,
  Factory,
  FlaskConical,
  GraduationCap,
  TriangleAlert,
} from 'lucide-react'
import type { MouseEvent, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { EvidenceKindBadge, Pill, StatusBadge, SyntheticBadge } from '@/components/badges'
import { Callout } from '@/components/cards'
import { PageHeader, SectionHeader } from '@/components/headers'
import { Button } from '@/components/ui/button'
import { HEALTH_WEIGHTS } from '@/lib/demo/courseHealth'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------- content
const SECTIONS = [
  { id: 'walkthrough', title: 'Demo walkthrough' },
  { id: 'data-sources', title: 'Data sources' },
  { id: 'demand', title: 'Demand score' },
  { id: 'supply', title: 'Training supply' },
  { id: 'openings', title: 'Estimated openings' },
  { id: 'mismatch', title: 'Mismatch ratio' },
  { id: 'course-health', title: 'Course health' },
  { id: 'evidence', title: 'Evidence labels' },
] as const

type SectionId = (typeof SECTIONS)[number]['id']

const STEPS: { title: string; text: string; to: string; cta: string }[] = [
  {
    title: 'Maharashtra overview',
    text: 'Start on the dashboard: the district map, the largest shortages and new recommendations.',
    to: '/dashboard',
    cta: 'Open overview',
  },
  {
    title: 'Nashik district',
    text: 'Open Nashik to see which roles have fewer trained candidates than estimated openings, and why.',
    to: '/districts/MH-NASHIK',
    cta: 'Open Nashik',
  },
  {
    title: 'EV Diagnostics skill',
    text: 'Follow the skill: its demand trend from job ads and surveys, and which courses teach it.',
    to: '/skills/ev-diagnostics',
    cta: 'Open skill',
  },
  {
    title: 'Electrician course at Example ITI A',
    text: 'Course health 42/100 (At risk) in the demo data: the syllabus has no EV Diagnostics module.',
    to: '/courses/nsk-iti-a-electrician',
    cta: 'Open course',
  },
  {
    title: 'Recommendation: Add EV Diagnostics module',
    text: 'Priority 91. Review the evidence items and the confidence label, then accept it.',
    to: '/recommendations/rec-nsk-ev-diagnostics',
    cta: 'Open recommendation',
  },
  {
    title: 'Employer validation and apprenticeships',
    text: 'As an employer, validate the recommendation and pledge 35 apprenticeship seats.',
    to: '/employer',
    cta: 'Open employer portal',
  },
  {
    title: 'Nashik district plan',
    text: 'The accepted recommendation and the pledge come together in the district plan.',
    to: '/district-plans',
    cta: 'Open district plans',
  },
]

const DATA_SOURCES: { icon: ReactNode; title: string; text: string }[] = [
  {
    icon: <BriefcaseBusiness aria-hidden />,
    title: 'Job postings',
    text: 'Online job ads matched to roles and skills. Their volume and growth make the posting signal.',
  },
  {
    icon: <ClipboardList aria-hidden />,
    title: 'Employer surveys',
    text: 'Headcounts employers say they need: the latest answer per employer from the last 12 months, recent answers weighted more.',
  },
  {
    icon: <Factory aria-hidden />,
    title: 'Industry events',
    text: 'Announced plants and expansions, turned into jobs expected over the following quarters.',
  },
  {
    icon: <GraduationCap aria-hidden />,
    title: 'Training and placement records',
    text: 'Seats, seats filled, completions and placements for each course offering.',
  },
]

const EVIDENCE_KINDS: {
  kind: 'OBSERVED' | 'INFERRED' | 'SYNTHETIC' | 'ASSUMPTION'
  text: string
}[] = [
  {
    kind: 'OBSERVED',
    text: 'Read directly from a stored record: a job ad, a survey answer, a placement record. (In this demo those records are themselves synthetic.)',
  },
  {
    kind: 'INFERRED',
    text: 'Calculated from observed records by a rule or model, such as a demand score or a skill trend.',
  },
  {
    kind: 'SYNTHETIC',
    text: 'Generated for the demo world to stand in for data that is not available.',
  },
  {
    kind: 'ASSUMPTION',
    text: 'A modelling choice made by the team (for example a coverage factor or a default completion rate), stored with the result so it can be checked.',
  },
]

// ---------------------------------------------------------------- building blocks
function Formula({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border bg-muted/50 px-4 py-3 font-mono text-sm leading-relaxed text-foreground">
      {children}
    </p>
  )
}

function Terms({ items }: { items: [term: ReactNode, meaning: ReactNode][] }) {
  return (
    <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[max-content_minmax(0,1fr)]">
      {items.map(([term, meaning], index) => (
        <div key={index} className="contents">
          <dt className="font-medium text-foreground">{term}</dt>
          <dd className="text-muted-foreground">{meaning}</dd>
        </div>
      ))}
    </dl>
  )
}

function Section({
  id,
  title,
  description,
  badge,
  children,
  className,
}: {
  id: SectionId
  title: string
  description?: ReactNode
  badge?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-heading`}
      className={cn('animate-in-up scroll-mt-24 rounded-xl border bg-card shadow-xs', className)}
    >
      <SectionHeader
        id={`${id}-heading`}
        title={title}
        description={description}
        actions={badge}
        className="border-b px-5 py-4"
      />
      <div className="space-y-4 p-5">{children}</div>
    </section>
  )
}

function jumpTo(event: MouseEvent<HTMLAnchorElement>, id: string) {
  const target = document.getElementById(id)
  if (!target) return
  event.preventDefault()
  target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  const heading = document.getElementById(`${id}-heading`)
  if (heading) {
    heading.setAttribute('tabindex', '-1')
    heading.focus({ preventScroll: true })
  }
}

// ---------------------------------------------------------------- page
export default function HelpPage() {
  const { t } = useTranslation()
  const w = HEALTH_WEIGHTS

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={t('pages.help')}
        title="How InnovProcure works"
        description="Where the numbers come from, how they are combined, and how to walk through the demo. Every figure in this prototype is computed from a synthetic demo world."
        badges={<SyntheticBadge />}
      />

      <Callout tone="demo" icon={<FlaskConical aria-hidden />} title="Method notes for a prototype">
        Weights and thresholds below are team assumptions kept in{' '}
        <code className="font-mono text-xs text-foreground">config/scoring.yaml</code> (each
        pipeline run stores the file&apos;s version and hash). They are not official government
        thresholds, and no number in this demo is an official statistic.
      </Callout>

      <div className="grid gap-6 lg:grid-cols-[13rem_minmax(0,1fr)]">
        <nav aria-label="On this page" className="lg:sticky lg:top-24 lg:self-start">
          <p className="mb-2 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
            On this page
          </p>
          <ul className="flex flex-wrap gap-1.5 lg:flex-col lg:gap-0.5">
            {SECTIONS.map((section) => (
              <li key={section.id}>
                <a
                  href={`#${section.id}`}
                  onClick={(event) => jumpTo(event, section.id)}
                  className="block rounded-md border px-2.5 py-1 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-2 lg:border-transparent lg:px-3 lg:py-1.5"
                >
                  {section.title}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="min-w-0 space-y-6">
          {/* ------------------------------------------------------------ walkthrough */}
          <Section
            id="walkthrough"
            title="Demo walkthrough"
            description="Seven steps that follow one story through the app: a Nashik EV skill gap, from signal to district plan."
          >
            <ol className="relative space-y-3">
              {STEPS.map((step, index) => (
                <li
                  key={step.to}
                  className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border px-4 py-3 transition-colors hover:border-primary/40"
                >
                  <span
                    className="grid size-8 shrink-0 place-items-center rounded-full bg-primary text-sm font-semibold text-primary-foreground"
                    aria-hidden
                  >
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1 basis-64">
                    <p className="font-medium">
                      <span className="sr-only">Step {index + 1}: </span>
                      {step.title}
                    </p>
                    <p className="text-sm text-muted-foreground">{step.text}</p>
                  </div>
                  <Button variant="outline" size="sm" asChild>
                    <Link to={step.to}>
                      {step.cta} <ArrowRight aria-hidden />
                    </Link>
                  </Button>
                </li>
              ))}
            </ol>
            <p className="text-sm text-muted-foreground">
              Tip: in{' '}
              <Link to="/admin" className="font-medium text-primary hover:underline">
                Demo Controls
              </Link>{' '}
              you can switch on the simulated Nashik EV expansion, and reset the demo to run the
              walkthrough again.
            </p>
          </Section>

          <div className="grid gap-6 2xl:grid-cols-2">
            {/* ---------------------------------------------------------- data sources */}
            <Section
              id="data-sources"
              title="Data sources"
              description="Four kinds of signal feed the analysis. All of them are synthetic in this demo."
              badge={<SyntheticBadge />}
            >
              <ul className="grid gap-3 sm:grid-cols-2">
                {DATA_SOURCES.map((source) => (
                  <li key={source.title} className="flex gap-3 rounded-lg border p-3">
                    <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-accent text-primary [&_svg]:size-4.5">
                      {source.icon}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium">{source.title}</p>
                      <p className="text-sm text-muted-foreground">{source.text}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </Section>

            {/* ---------------------------------------------------------- demand */}
            <Section
              id="demand"
              title="Demand score"
              description="0–100 for each job role, district and quarter."
            >
              <Formula>
                D = 0.35·Postings + 0.25·Survey + 0.20·Growth events + 0.20·Absorption
              </Formula>
              <Terms
                items={[
                  ['Postings', 'Volume and growth of job ads for the role, as percentiles.'],
                  ['Survey', 'Headcounts employers asked for in recent surveys.'],
                  [
                    'Growth events',
                    'Jobs expected from announced industry events in the next 4 quarters.',
                  ],
                  ['Absorption', 'How readily past trainees were placed in the role.'],
                ]}
              />
              <p className="text-sm text-muted-foreground">
                If a part has no data for a role and district, the remaining weights are
                renormalised to add up to 1 again and the confidence label is lowered. Weights come
                from <code className="font-mono text-xs text-foreground">config/scoring.yaml</code>.
              </p>
            </Section>

            {/* ---------------------------------------------------------- supply */}
            <Section
              id="supply"
              title="Training supply"
              description="Trained candidates per role and district, over the offerings that train for it."
            >
              <Formula>Supply = seats filled × completion rate</Formula>
              <p className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                When an offering has no completion data, a rate of 0.8 is used and stored next to
                the result as an
                <EvidenceKindBadge kind="ASSUMPTION" />
              </p>
            </Section>

            {/* ---------------------------------------------------------- openings */}
            <Section
              id="openings"
              title="Estimated openings"
              description="Openings per year for a role and district."
            >
              <Formula>Openings / yr = postings in the last 4 quarters ÷ coverage factor</Formula>
              <Terms
                items={[
                  [
                    <span key="f" className="font-mono">
                      0.3
                    </span>,
                    'Formal-heavy roles: most hiring is advertised (the default for every role).',
                  ],
                  [
                    <span key="i" className="font-mono">
                      0.1
                    </span>,
                    'Informal-heavy roles: most hiring happens by word of mouth.',
                  ],
                ]}
              />
              <Callout
                tone="warning"
                icon={<TriangleAlert aria-hidden />}
                title="A modelling assumption, not an official statistic"
              >
                Only part of real hiring shows up as online job ads. The coverage factor is the
                team&apos;s estimate of that share, to be calibrated later against official labour
                statistics.
              </Callout>
            </Section>

            {/* ---------------------------------------------------------- mismatch */}
            <Section
              id="mismatch"
              title="Mismatch ratio"
              description="Compares trained candidates with estimated openings."
            >
              <Formula>R = supply ÷ estimated openings</Formula>
              <ul className="grid gap-2 sm:grid-cols-3">
                <li className="flex flex-col gap-1.5 rounded-lg border p-3">
                  <StatusBadge status="UNDER_SUPPLIED" className="self-start" />
                  <span className="font-mono text-sm">R &lt; 0.7</span>
                </li>
                <li className="flex flex-col gap-1.5 rounded-lg border p-3">
                  <StatusBadge status="BALANCED" className="self-start" />
                  <span className="font-mono text-sm">0.7 ≤ R ≤ 1.5</span>
                </li>
                <li className="flex flex-col gap-1.5 rounded-lg border p-3">
                  <StatusBadge status="OVER_SUPPLIED" className="self-start" />
                  <span className="font-mono text-sm">R &gt; 1.5</span>
                </li>
              </ul>
              <p className="text-sm text-muted-foreground">
                <span className="font-medium text-foreground">District mismatch</span> is the
                demand-weighted mean of <span className="font-mono">|ln R|</span> over the
                district&apos;s roles: 0 means supply matches openings, and higher means a larger
                gap in either direction.
              </p>
            </Section>

            {/* ---------------------------------------------------------- course health */}
            <Section
              id="course-health"
              title="Course health"
              description="0–100 for each course offering."
              badge={<Pill>Demo heuristic</Pill>}
            >
              <Formula>
                Health = {w.alignment.toFixed(2)}·Demand alignment + {w.emerging.toFixed(2)}
                ·Emerging-skill coverage + {w.placement.toFixed(2)}·Placement rate +{' '}
                {w.freshness.toFixed(2)}·Curriculum freshness
              </Formula>
              <Terms
                items={[
                  [
                    'Demand alignment',
                    "How many of the district's most demanded skills the syllabus teaches.",
                  ],
                  [
                    'Emerging-skill coverage',
                    "The district's emerging skills that the syllabus teaches.",
                  ],
                  ['Placement rate', 'Placed ÷ completed.'],
                  ['Curriculum freshness', 'Share of hours not spent on declining skills.'],
                ]}
              />
              <ul className="flex flex-wrap gap-2 text-sm">
                <li className="flex items-center gap-2 rounded-lg border px-3 py-2">
                  <StatusBadge status="HEALTHY" /> <span className="font-mono">≥ 70</span>
                </li>
                <li className="flex items-center gap-2 rounded-lg border px-3 py-2">
                  <StatusBadge status="WATCH" /> <span className="font-mono">50–69</span>
                </li>
                <li className="flex items-center gap-2 rounded-lg border px-3 py-2">
                  <StatusBadge status="AT_RISK" /> <span className="font-mono">&lt; 50</span>
                </li>
              </ul>
              <p className="text-sm text-muted-foreground">
                A demo heuristic calculated in the browser (the backend has no course-health
                endpoint yet), not an official rating of any institute.
              </p>
            </Section>

            {/* ---------------------------------------------------------- evidence */}
            <Section
              id="evidence"
              title="Evidence labels"
              description="Every reason shown next to a number carries one of these labels."
              className="2xl:col-span-2"
            >
              <ul className="grid gap-3 md:grid-cols-2">
                {EVIDENCE_KINDS.map((item) => (
                  <li key={item.kind} className="flex flex-col gap-2 rounded-lg border p-3">
                    <EvidenceKindBadge kind={item.kind} />
                    <p className="text-sm text-muted-foreground">{item.text}</p>
                  </li>
                ))}
              </ul>
            </Section>
          </div>
        </div>
      </div>
    </div>
  )
}
