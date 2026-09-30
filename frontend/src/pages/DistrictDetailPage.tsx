import { ArrowRight, Factory, GraduationCap, MoveRight, Scale, TriangleAlert } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { useFilters } from '@/app/filters'
import { ConfidenceBadge, DataSourceBadge, Pill, StatusBadge } from '@/components/badges'
import {
  Callout,
  CourseHealthCard,
  EvidenceCard,
  MetricCard,
  SkillGapCard,
} from '@/components/cards'
import { DemandChart, GapChart } from '@/components/charts'
import { PageHeader, Panel } from '@/components/headers'
import { EmptyState, ErrorState, LoadingState, QueryState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  useCourses,
  useDistrictMismatch,
  useRoleDemand,
  useRoleHistory,
  useSkillDemand,
} from '@/lib/api/queries'
import { coursesTeaching } from '@/lib/api/skillsApi'
import type { Assumption, Offering, RoleMismatch } from '@/lib/api/types'
import { useDemoState } from '@/lib/demo/store'
import { mismatchTone, reasonToEvidence } from '@/lib/evidence'
import { districtName, fmtInt, fmtRatio, fmtScore } from '@/lib/format'
import { cn } from '@/lib/utils'

function offeringsOf(item: RoleMismatch): Offering[] {
  const supply = item.observed_inputs.supply as { offerings?: Offering[] } | undefined
  return supply?.offerings ?? []
}

function assumptionValue(a: Assumption): string {
  if (typeof a.value === 'string' || typeof a.value === 'number') return String(a.value)
  if (a.value && typeof a.value === 'object') {
    return Object.entries(a.value as Record<string, unknown>)
      .map(([k, v]) => `${k.replace(/_/g, ' ')} ${String(v)}`)
      .join(', ')
  }
  return '-'
}

/** One row of the Industry -> Training gap visual. */
function GapRow({
  item,
  selected,
  onSelect,
}: {
  item: RoleMismatch
  selected: boolean
  onSelect: () => void
}) {
  const offerings = offeringsOf(item)
  const shortBy = Math.max(0, item.estimated_openings - item.supply)
  const max = Math.max(item.estimated_openings, item.supply, 1)
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        className={cn(
          'grid w-full gap-3 rounded-xl border p-4 text-left transition-colors focus-visible:outline-2 md:grid-cols-[1.2fr_auto_0.9fr_auto_1.2fr] md:items-center',
          selected
            ? 'border-primary bg-accent/50 ring-1 ring-primary/30'
            : 'bg-card hover:border-primary/40',
        )}
      >
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <Factory className="size-4 text-primary" aria-hidden />
            <p className="font-medium">{item.role.title}</p>
          </div>
          <p className="text-xs text-muted-foreground">
            Demand {fmtScore(item.demand_score)}/100 · ~{fmtInt(item.estimated_openings)} est.
            openings / yr
          </p>
          <div className="h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
            <div
              className="h-full rounded-full bg-chart-1"
              style={{ width: `${(item.estimated_openings / max) * 100}%` }}
            />
          </div>
        </div>
        <MoveRight className="hidden size-5 text-muted-foreground md:block" aria-hidden />
        <div className="flex flex-col items-start gap-1 md:items-center md:text-center">
          <StatusBadge status={item.status} />
          <p className="tabular text-xs text-muted-foreground">
            ratio {fmtRatio(item.ratio)}
            {item.status === 'UNDER_SUPPLIED' && ` · short by ~${fmtInt(shortBy)}`}
          </p>
        </div>
        <MoveRight className="hidden size-5 text-muted-foreground md:block" aria-hidden />
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <GraduationCap className="size-4 text-chart-3" aria-hidden />
            <p className="font-medium">{fmtInt(item.supply)} trained / yr</p>
          </div>
          <p className="truncate text-xs text-muted-foreground">
            {offerings.length
              ? offerings.map((o) => o.institute_name.replace(/,.*$/, '')).join(', ')
              : 'No local course trains for this role'}
          </p>
          <div className="h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
            <div
              className="h-full rounded-full bg-chart-3"
              style={{ width: `${(item.supply / max) * 100}%` }}
            />
          </div>
        </div>
      </button>
    </li>
  )
}

export default function DistrictDetailPage() {
  const { district = '' } = useParams()
  const filters = useFilters()
  const demo = useDemoState()
  const quarter = filters.api.quarter
  const summary = useDistrictMismatch(district, quarter)
  const roleDemand = useRoleDemand({ district, quarter })
  const skills = useSkillDemand({ district, quarter })
  const courses = useCourses()
  const history = useRoleHistory(district)
  const [selectedRole, setSelectedRole] = useState<string | null>(null)

  const roles = useMemo(() => {
    const list = summary.data?.data.roles ?? []
    const filtered =
      filters.sector === 'ALL' ? list : list.filter((r) => r.role.sector === filters.sector)
    return [...filtered].sort(
      (a, b) =>
        (b.demand_score ?? 0) * (b.abs_log_ratio ?? 0) -
        (a.demand_score ?? 0) * (a.abs_log_ratio ?? 0),
    )
  }, [summary.data, filters.sector])

  const active = roles.find((r) => r.role.code === selectedRole) ?? roles[0]
  const activeDemand = roleDemand.data?.data.items.find((d) => d.role.code === active?.role.code)
  const evidence = useMemo(() => {
    const reasons = [...(active?.reasons ?? [])]
    for (const r of activeDemand?.reasons ?? []) {
      if (!reasons.some((x) => x.code === r.code && x.text === r.text)) reasons.push(r)
    }
    return reasons.map(reasonToEvidence)
  }, [active, activeDemand])
  const assumptions = active?.assumptions ?? []

  const topSkills = useMemo(
    () =>
      [...(skills.data?.data.items ?? [])]
        .sort((a, b) => b.demand_score - a.demand_score)
        .slice(0, 8),
    [skills.data],
  )
  const districtCourses = (courses.data?.data ?? []).filter((c) => c.district.code === district)

  const historyRoles = useMemo(() => {
    const points = history.data?.data ?? []
    const last = points[points.length - 1]?.quarter
    return points
      .filter((p) => p.quarter === last)
      .sort((a, b) => b.score - a.score)
      .slice(0, 5)
      .map((p) => p.role)
  }, [history.data])
  const chartData = useMemo(() => {
    const rows = new Map<string, Record<string, string | number | null>>()
    for (const p of history.data?.data ?? []) {
      if (!historyRoles.includes(p.role)) continue
      const row = rows.get(p.quarter) ?? { quarter: p.quarter }
      row[p.role] = p.score
      rows.set(p.quarter, row)
    }
    return [...rows.values()]
  }, [history.data, historyRoles])
  const titles = Object.fromEntries(
    (summary.data?.data.roles ?? []).map((r) => [r.role.code, r.role.title]),
  )

  if (summary.isPending) return <LoadingState rows={6} />
  if (summary.isError) return <ErrorState error={summary.error} onRetry={() => summary.refetch()} />
  const data = summary.data.data
  const openings = data.roles.reduce((sum, r) => sum + r.estimated_openings, 0)
  const trained = data.roles.reduce((sum, r) => sum + r.supply, 0)
  const topDemand = [...(roleDemand.data?.data.items ?? [])].sort(
    (a, b) => b.demand_score - a.demand_score,
  )[0]

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={`District Intelligence · ${data.quarter}`}
        title={data.district.name}
        description="How the district's training supply compares with what employers are hiring for, and the evidence behind each gap."
        badges={
          <>
            <Pill tone={mismatchTone(data.mismatch_score)}>
              Mismatch {fmtScore(data.mismatch_score)}
            </Pill>
            <DataSourceBadge source={summary.data.source} note={summary.data.note} />
          </>
        }
        actions={
          <Button variant="outline" asChild>
            <Link to="/district-plans">District plan</Link>
          </Button>
        }
      />

      {demo.evExpansionSimulated && district === 'MH-NASHIK' && (
        <Callout tone="danger" title="Simulated event active" icon={<Factory aria-hidden />}>
          EV battery-pack assembly unit (simulated, synthetic): about 180 EV Service Technician jobs
          expected in {districtName(district)} in 2026Q4-2027Q3. The gap below already includes it.
        </Callout>
      )}

      <section
        aria-label="District indicators"
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        <MetricCard
          label="Mismatch score"
          value={fmtScore(data.mismatch_score)}
          hint="0 = balanced; higher = bigger gaps (demand-weighted)"
          icon={<Scale aria-hidden />}
          tone={mismatchTone(data.mismatch_score) === 'danger' ? 'danger' : 'warning'}
        />
        <MetricCard
          label="Roles in shortage"
          value={`${data.status_counts.UNDER_SUPPLIED ?? 0} / ${data.roles.length}`}
          hint={`${data.status_counts.OVER_SUPPLIED ?? 0} oversupplied, ${data.status_counts.BALANCED ?? 0} balanced`}
          icon={<TriangleAlert aria-hidden />}
          tone="danger"
        />
        <MetricCard
          label="Estimated openings / yr"
          value={fmtInt(openings)}
          hint={`vs ${fmtInt(trained)} trained a year (openings are a model estimate)`}
          icon={<Factory aria-hidden />}
        />
        <MetricCard
          label="Highest demand role"
          value={topDemand ? fmtScore(topDemand.demand_score) : '-'}
          hint={
            topDemand
              ? `${topDemand.role.title} · ${topDemand.confidence.toLowerCase()} confidence`
              : undefined
          }
          icon={<GraduationCap aria-hidden />}
          tone="info"
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-12">
        <Panel
          className="xl:col-span-7"
          title="Industry → Training gap"
          description="Estimated openings employers need each year vs people local courses train. Select a role to see why."
        >
          {roles.length === 0 ? (
            <EmptyState description="No roles for this sector in this district." />
          ) : (
            <Tabs defaultValue="flow">
              <TabsList className="mb-4">
                <TabsTrigger value="flow">Gap view</TabsTrigger>
                <TabsTrigger value="chart">Chart</TabsTrigger>
              </TabsList>
              <TabsContent value="flow">
                <div className="mb-2 hidden grid-cols-[1.2fr_auto_0.9fr_auto_1.2fr] gap-3 px-4 text-xs font-semibold tracking-wide text-muted-foreground uppercase md:grid">
                  <span>Industry needs</span>
                  <span className="w-5" />
                  <span className="text-center">Gap</span>
                  <span className="w-5" />
                  <span>Training supply</span>
                </div>
                <ul className="space-y-2">
                  {roles.map((item) => (
                    <GapRow
                      key={item.role.code}
                      item={item}
                      selected={item.role.code === active?.role.code}
                      onSelect={() => setSelectedRole(item.role.code)}
                    />
                  ))}
                </ul>
              </TabsContent>
              <TabsContent value="chart">
                <GapChart
                  data={roles.map((r) => ({
                    name: r.role.title,
                    openings: Math.round(r.estimated_openings),
                    supply: Math.round(r.supply),
                  }))}
                />
              </TabsContent>
            </Tabs>
          )}
        </Panel>

        <div className="space-y-4 xl:col-span-5">
          {active && (
            <div className="rounded-xl border bg-card p-5 shadow-xs">
              <p className="text-xs font-semibold tracking-wide text-primary uppercase">
                Selected role
              </p>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold">{active.role.title}</h2>
                <StatusBadge status={active.status} />
                <ConfidenceBadge confidence={active.confidence} />
              </div>
              <dl className="mt-4 grid grid-cols-3 gap-3 text-center">
                <div className="rounded-lg bg-muted p-3">
                  <dt className="text-xs text-muted-foreground">Demand</dt>
                  <dd className="tabular text-xl font-semibold">{fmtScore(active.demand_score)}</dd>
                </div>
                <div className="rounded-lg bg-muted p-3">
                  <dt className="text-xs text-muted-foreground">Trained / yr</dt>
                  <dd className="tabular text-xl font-semibold">{fmtInt(active.supply)}</dd>
                </div>
                <div className="rounded-lg bg-muted p-3">
                  <dt className="text-xs text-muted-foreground">Est. openings</dt>
                  <dd className="tabular text-xl font-semibold">
                    {fmtInt(active.estimated_openings)}
                  </dd>
                </div>
              </dl>
            </div>
          )}
          <EvidenceCard items={evidence} title="Why this matters" />
          {assumptions.length > 0 && (
            <details className="group rounded-xl border bg-card shadow-xs">
              <summary className="cursor-pointer list-none px-5 py-3.5 text-sm font-semibold focus-visible:outline-2">
                Assumptions used ({assumptions.length})
                <span className="ml-2 text-xs font-normal text-muted-foreground">
                  modelling choices, not official statistics
                </span>
              </summary>
              <ul className="divide-y border-t text-sm">
                {assumptions.map((a) => (
                  <li key={a.name} className="px-5 py-2.5">
                    <p className="font-medium capitalize">{a.name}</p>
                    <p className="text-muted-foreground">{assumptionValue(a)}</p>
                    <p className="text-xs text-muted-foreground/80">{a.source}</p>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      </div>

      <Panel
        title="Skills employers are asking for"
        description="Demand score from job-ad mentions in this district; flagged when no local course teaches the skill to intermediate level."
        actions={<DataSourceBadge source={skills.data?.source} note={skills.data?.note} />}
      >
        <QueryState query={skills} isEmpty={(d) => d.data.items.length === 0}>
          {() => (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {topSkills.map((s) => {
                const local = coursesTeaching(s.skill.code).filter(
                  (c) => c.district.code === district && c.band >= 2,
                )
                return (
                  <SkillGapCard
                    key={s.skill.code}
                    skill={s.skill}
                    demandScore={s.demand_score}
                    trend={s.trend_status}
                    postings={s.mention_count}
                    taught={local.length ? undefined : 'Not taught locally'}
                    href={`/skills/${s.skill.code}`}
                  />
                )
              })}
            </div>
          )}
        </QueryState>
      </Panel>

      <div className="grid gap-6 xl:grid-cols-12">
        <Panel
          className="xl:col-span-7"
          title="Courses in this district"
          description="Course health against this district's skill demand (demo heuristic)."
          actions={
            <>
              <DataSourceBadge source={courses.data?.source} note={courses.data?.note} />
              <Button variant="outline" size="sm" asChild>
                <Link to="/courses">
                  All courses <ArrowRight aria-hidden />
                </Link>
              </Button>
            </>
          }
        >
          <QueryState query={courses} isEmpty={() => districtCourses.length === 0}>
            {() => (
              <div className="grid gap-3 md:grid-cols-2">
                {[...districtCourses]
                  .sort((a, b) => a.health_score - b.health_score)
                  .map((c) => (
                    <CourseHealthCard key={c.id} course={c} />
                  ))}
              </div>
            )}
          </QueryState>
        </Panel>
        <Panel
          className="xl:col-span-5"
          title="Role demand over time"
          description="Demand score (0-100) by quarter."
          actions={<DataSourceBadge source={history.data?.source} note={history.data?.note} />}
        >
          <QueryState query={history} isEmpty={(d) => d.data.length === 0}>
            {() => (
              <DemandChart
                data={chartData}
                series={historyRoles.map((code) => ({ key: code, label: titles[code] ?? code }))}
                height={300}
              />
            )}
          </QueryState>
        </Panel>
      </div>
    </div>
  )
}
