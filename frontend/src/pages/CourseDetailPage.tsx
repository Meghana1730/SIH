import { ArrowRight, Building2, Check, Clock, GraduationCap, Send, Users, X } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import {
  ConfidenceBadge,
  DataSourceBadge,
  Pill,
  StatusBadge,
  SyntheticBadge,
  TrendBadge,
} from '@/components/badges'
import {
  Callout,
  EvidenceCard,
  MetricCard,
  RecommendationCard,
  ScoreRing,
  SkillGapCard,
} from '@/components/cards'
import { DataTable } from '@/components/DataTable'
import { PageHeader, Panel } from '@/components/headers'
import { EmptyState, ErrorState, LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import {
  useCourse,
  useRecommendations,
  useRoleDemand,
  useSetRecommendationStatus,
} from '@/lib/api/queries'
import type { CurriculumSkill, Recommendation } from '@/lib/api/types'
import { HEALTH_WEIGHTS } from '@/lib/demo/courseHealth'
import { reasonToEvidence } from '@/lib/evidence'
import { bandLabel, fmtPct, fmtScore } from '@/lib/format'
import { cn } from '@/lib/utils'

function BandMeter({ band }: { band: number }) {
  return (
    <div className="flex items-center gap-2" aria-label={`Taught: ${bandLabel(band)}`}>
      <div className="flex gap-0.5" aria-hidden>
        {[1, 2, 3].map((level) => (
          <span
            key={level}
            className={cn('h-2 w-5 rounded-sm', level <= band ? 'bg-primary' : 'bg-muted')}
          />
        ))}
      </div>
      <span
        className={cn('text-xs', band === 0 ? 'font-medium text-danger' : 'text-muted-foreground')}
      >
        {bandLabel(band)}
      </span>
    </div>
  )
}

function isGap(row: CurriculumSkill): boolean {
  return row.band_taught < 2 && ((row.demand_score ?? 0) >= 60 || row.trend === 'EMERGING')
}

function RecommendationWithActions({ rec }: { rec: Recommendation }) {
  const navigate = useNavigate()
  const setStatus = useSetRecommendationStatus()
  const [open, setOpen] = useState(rec.priority_score >= 90)
  const decide = (status: Recommendation['status'], message: string) =>
    setStatus.mutate({ id: rec.id, status }, { onSuccess: () => toast.success(message) })
  return (
    <div className="space-y-3">
      <RecommendationCard
        rec={rec}
        actions={
          <Button variant="ghost" size="sm" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
            {open ? 'Hide evidence' : 'Show evidence'}
          </Button>
        }
      />
      {open && (
        <div className="space-y-3 pl-4">
          <EvidenceCard
            title="Evidence for this recommendation"
            items={rec.evidence.map((e) => ({
              title: e.label,
              detail: e.detail,
              kind: e.kind,
              source: e.source,
            }))}
          />
          <p className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">Expected impact:</span>{' '}
            {rec.expected_impact}
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={rec.status === 'ACCEPTED' || setStatus.isPending}
              onClick={() => decide('ACCEPTED', `Accepted: ${rec.title}`)}
            >
              <Check aria-hidden /> {rec.status === 'ACCEPTED' ? 'Accepted' : 'Accept'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={rec.status === 'IN_REVIEW' || setStatus.isPending}
              onClick={() => {
                decide('IN_REVIEW', 'Sent to employers for validation')
                navigate('/employer', { state: { recommendationId: rec.id } })
              }}
            >
              <Send aria-hidden /> Ask employers to validate
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={rec.status === 'DISMISSED' || setStatus.isPending}
              onClick={() => decide('DISMISSED', 'Recommendation dismissed')}
            >
              <X aria-hidden /> Dismiss
            </Button>
            <Button size="sm" variant="link" asChild>
              <Link to={`/recommendations/${rec.id}`}>Open in decision inbox</Link>
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function CourseDetailPage() {
  const { courseId } = useParams()
  const course = useCourse(courseId)
  const recommendations = useRecommendations()
  const c = course.data?.data ?? null
  const topRec = (recommendations.data?.data ?? []).find((r) =>
    c?.recommendation_ids.includes(r.id),
  )
  const liveDemand = useRoleDemand(
    c ? { district: c.district.code, sector: topRec?.sector ?? c.sector } : {},
  )

  if (course.isPending) return <LoadingState rows={6} />
  if (course.isError) return <ErrorState error={course.error} onRetry={() => course.refetch()} />
  if (!c) {
    return (
      <EmptyState
        title="Course not found"
        description="This course is not in the demo catalogue."
        action={
          <Button asChild variant="outline">
            <Link to="/courses">Back to courses</Link>
          </Button>
        }
      />
    )
  }

  const recs = (recommendations.data?.data ?? []).filter((r) => c.recommendation_ids.includes(r.id))
  const demandItem = [...(liveDemand.data?.data.items ?? [])]
    .filter((d) => d.district.code === c.district.code)
    .sort((a, b) => b.demand_score - a.demand_score)[0]
  const gaps = c.missing_skills.length

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={`Course health · ${c.district.name}`}
        title={c.name}
        description={
          <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="inline-flex items-center gap-1">
              <Building2 className="size-4" aria-hidden /> {c.institute.name}
            </span>
            <span>Trains for: {c.primary_role.title}</span>
          </span>
        }
        badges={
          <>
            <StatusBadge status={c.health_status} />
            <DataSourceBadge source={course.data?.source} note={course.data?.note} />
          </>
        }
        actions={
          <Button asChild>
            <a href="#recommended-changes">
              Recommended changes <ArrowRight aria-hidden />
            </a>
          </Button>
        }
      />

      <div className="grid gap-6 xl:grid-cols-12">
        <section
          aria-label="Course health score"
          className={cn(
            'rounded-xl border p-6 shadow-xs xl:col-span-5',
            c.health_status === 'AT_RISK' ? 'border-danger/30 bg-danger-soft/60' : 'bg-card',
          )}
        >
          <div className="flex flex-wrap items-center gap-6">
            <ScoreRing score={c.health_score} size={128} label="Course health" />
            <div className="min-w-0 flex-1 space-y-2">
              <p className="text-sm font-medium text-muted-foreground">Course health</p>
              <p className="text-3xl font-semibold tracking-tight">
                {c.health_score}
                <span className="text-lg text-muted-foreground">/100</span>
              </p>
              <StatusBadge status={c.health_status} className="h-7 px-3 text-sm uppercase" />
              <p className="text-sm text-muted-foreground">
                {gaps} high-demand skill{gaps === 1 ? '' : 's'} not taught to intermediate level.
              </p>
            </div>
          </div>
          <ul className="mt-6 space-y-3" aria-label="Health score components">
            {c.health_components.map((component) => (
              <li key={component.name}>
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span className="font-medium">
                    {component.name}{' '}
                    <span className="text-xs font-normal text-muted-foreground">
                      weight {component.weight}
                    </span>
                  </span>
                  <span className="tabular text-muted-foreground">
                    {component.value.toFixed(0)}/100 →{' '}
                    {(component.value * component.weight).toFixed(1)} pts
                  </span>
                </div>
                <div className="mt-1 h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
                  <div
                    className={cn(
                      'h-full rounded-full',
                      component.value >= 70
                        ? 'bg-success'
                        : component.value >= 50
                          ? 'bg-warning'
                          : 'bg-danger',
                    )}
                    style={{ width: `${component.value}%` }}
                  />
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{component.note}</p>
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs text-muted-foreground">
            Health = {HEALTH_WEIGHTS.alignment} × alignment + {HEALTH_WEIGHTS.emerging} × emerging
            coverage + {HEALTH_WEIGHTS.placement} × placement + {HEALTH_WEIGHTS.freshness} ×
            freshness. A demo heuristic computed in the browser, not an official rating.
          </p>
        </section>

        <div className="space-y-6 xl:col-span-7">
          <section aria-label="Course facts" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricCard
              label="Seats filled"
              value={`${c.seats_filled}/${c.seats}`}
              icon={<Users aria-hidden />}
            />
            <MetricCard
              label="Completion"
              value={fmtPct(c.completion_rate)}
              icon={<GraduationCap aria-hidden />}
              tone="info"
            />
            <MetricCard
              label="Placement"
              value={fmtPct(c.placement_rate)}
              icon={<Check aria-hidden />}
              tone={c.placement_rate >= 0.6 ? 'success' : 'warning'}
            />
            <MetricCard
              label="Duration"
              value={`${c.duration_hours} h`}
              icon={<Clock aria-hidden />}
            />
          </section>

          <Panel
            title="Missing skills"
            description={`Skills ${c.district.name} employers ask for that this course does not teach to intermediate level.`}
            actions={<SyntheticBadge />}
          >
            {c.missing_skills.length === 0 ? (
              <EmptyState title="No missing high-demand skills" />
            ) : (
              <div className="grid gap-3 sm:grid-cols-2">
                {c.missing_skills.slice(0, 6).map((m) => (
                  <SkillGapCard
                    key={m.skill.code}
                    skill={m.skill}
                    demandScore={m.demand_score}
                    trend={m.trend}
                    postings={m.postings}
                    taught={(() => {
                      const band =
                        c.curriculum.find((s) => s.skill.code === m.skill.code)?.band_taught ?? 0
                      return band
                        ? `Taught at ${bandLabel(band).toLowerCase()} level only`
                        : 'Not taught'
                    })()}
                    href={`/skills/${m.skill.code}`}
                  />
                ))}
              </div>
            )}
          </Panel>
        </div>
      </div>

      <Panel
        title="Curriculum vs demand"
        description={`Each skill's demand score in ${c.district.name} next to how deeply the course teaches it.`}
        actions={<DataSourceBadge source={course.data?.source} note={course.data?.note} />}
      >
        <DataTable
          rows={c.curriculum}
          rowKey={(r) => r.skill.code}
          caption="Curriculum versus district demand"
          initialSort={{ key: 'demand', desc: true }}
          columns={[
            {
              key: 'skill',
              header: 'Skill',
              sortValue: (r) => r.skill.name,
              cell: (r) => (
                <Link
                  to={`/skills/${r.skill.code}`}
                  className="font-medium hover:text-primary hover:underline"
                >
                  {r.skill.name}
                </Link>
              ),
            },
            {
              key: 'demand',
              header: 'District demand',
              sortValue: (r) => r.demand_score,
              cell: (r) => (
                <div className="flex items-center gap-2">
                  <div className="h-2 w-24 overflow-hidden rounded-full bg-muted" aria-hidden>
                    <div
                      className="h-full rounded-full bg-chart-1"
                      style={{ width: `${r.demand_score ?? 0}%` }}
                    />
                  </div>
                  <span className="tabular text-sm">{fmtScore(r.demand_score)}</span>
                </div>
              ),
            },
            { key: 'trend', header: 'Trend', cell: (r) => <TrendBadge trend={r.trend} /> },
            {
              key: 'band',
              header: 'Taught',
              sortValue: (r) => r.band_taught,
              cell: (r) => <BandMeter band={r.band_taught} />,
            },
            {
              key: 'hours',
              header: 'Hours',
              align: 'right',
              sortValue: (r) => r.hours,
              cell: (r) => (r.hours ? r.hours : '-'),
            },
            {
              key: 'gap',
              header: 'Fit',
              cell: (r) =>
                isGap(r) ? (
                  <Pill tone="danger">Gap</Pill>
                ) : r.trend === 'DECLINING' && r.band_taught > 0 ? (
                  <Pill tone="warning">Declining content</Pill>
                ) : r.band_taught > 0 ? (
                  <Pill tone="success">Covered</Pill>
                ) : (
                  <Pill>Low demand</Pill>
                ),
            },
          ]}
        />
      </Panel>

      <div className="grid gap-6 xl:grid-cols-12" id="recommended-changes">
        <Panel
          className="xl:col-span-7"
          title="Recommended changes"
          description="Ranked by priority. Each recommendation lists the evidence it rests on."
          actions={
            <DataSourceBadge
              source={recommendations.data?.source}
              note={recommendations.data?.note}
            />
          }
        >
          {recs.length === 0 ? (
            <EmptyState title="No recommendations for this course" />
          ) : (
            <div className="space-y-4">
              {recs.map((rec) => (
                <RecommendationWithActions key={rec.id} rec={rec} />
              ))}
            </div>
          )}
        </Panel>
        <div className="space-y-4 xl:col-span-5">
          {demandItem ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <DataSourceBadge source={liveDemand.data?.source} note={liveDemand.data?.note} />
                <ConfidenceBadge confidence={demandItem.confidence} />
              </div>
              <EvidenceCard
                title={`Demand evidence: ${demandItem.role.title} in ${demandItem.district.name} (${fmtScore(demandItem.demand_score)}/100)`}
                items={demandItem.reasons.map(reasonToEvidence)}
              />
            </>
          ) : liveDemand.isPending ? (
            <LoadingState />
          ) : null}
          <Callout tone="demo" title="About this page">
            The course catalogue and recommendations are demo data (the backend has no course API
            yet). District skill demand and the evidence above come from the analytics engine when
            the API is reachable.
          </Callout>
        </div>
      </div>
    </div>
  )
}
