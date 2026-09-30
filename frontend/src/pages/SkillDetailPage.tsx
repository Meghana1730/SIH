// Skill detail: demand per district, trend over quarters, the evidence behind the score and
// which demo courses teach the skill. Demand is from the analytics engine (synthetic demo world);
// the course catalogue is frontend demo data.
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  GraduationCap,
  MapPin,
  Newspaper,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { useFilters } from '@/app/filters'
import type { Column } from '@/components/DataTable'
import { DataTable } from '@/components/DataTable'
import { ConfidenceBadge, DataSourceBadge, Pill, TrendBadge, type Tone } from '@/components/badges'
import { DemandChart } from '@/components/charts'
import { Callout, EvidenceCard, MetricCard } from '@/components/cards'
import { PageHeader, Panel } from '@/components/headers'
import { EmptyState, QueryState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { SkillHistoryPoint } from '@/lib/api/analyticsApi'
import { useSkillDetail, useSkillHistory } from '@/lib/api/queries'
import { coursesTeaching } from '@/lib/api/skillsApi'
import type { Assumption, DistrictRef, SkillDemand } from '@/lib/api/types'
import { SKILL_NAMES, skillSector } from '@/lib/demo/catalog'
import { reasonToEvidence } from '@/lib/evidence'
import { bandLabel, districtName, fmtInt, fmtScore, sectorLabel } from '@/lib/format'
import { cn } from '@/lib/utils'

type Metric = 'score' | 'mentions'
type TaughtCourse = ReturnType<typeof coursesTeaching>[number]

const CATALOGUE_NOTE = 'Course catalogue is demo data (no course API yet).'

function titleCase(text: string): string {
  const lower = text.toLowerCase()
  return lower.charAt(0).toUpperCase() + lower.slice(1)
}

/** Assumption values are numbers, strings or small objects; show them as one readable line. */
function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'number') return String(value)
  if (typeof value === 'string') return value
  if (typeof value === 'boolean') return value ? 'yes' : 'no'
  if (Array.isArray(value)) return value.map(formatValue).join(', ')
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, v]) => `${key.replace(/_/g, ' ')} ${formatValue(v)}`)
      .join(', ')
  }
  return String(value)
}

/** [{ quarter, 'MH-NASHIK': value, ... }] for DemandChart. */
function pivot(points: SkillHistoryPoint[], metric: Metric) {
  const quarters = [...new Set(points.map((p) => p.quarter))].sort()
  return quarters.map((quarter) => {
    const row: Record<string, string | number | null> = { quarter }
    for (const point of points) {
      if (point.quarter === quarter) row[point.district] = point[metric]
    }
    return row
  })
}

function bandTone(band: number): Tone {
  if (band >= 3) return 'success'
  if (band === 2) return 'info'
  return 'warning'
}

export default function SkillDetailPage() {
  const { skill: code = '' } = useParams()
  const filters = useFilters()
  const detailQuery = useSkillDetail(code || undefined, filters.api.quarter)
  const historyQuery = useSkillHistory({ skill: code })
  const [metric, setMetric] = useState<Metric>('score')
  const [evidenceDistrict, setEvidenceDistrict] = useState<string | null>(null)

  const items = useMemo(
    () => [...(detailQuery.data?.data.items ?? [])].sort((a, b) => b.demand_score - a.demand_score),
    [detailQuery.data],
  )
  const top = items[0]
  const name = top?.skill.name ?? SKILL_NAMES[code] ?? code
  const known = Boolean(top || SKILL_NAMES[code])
  const quarter = top?.quarter ?? detailQuery.data?.data.quarter ?? null
  const emergingIn = items.filter((i) => i.trend_status === 'EMERGING')
  const evidenceItem = items.find((i) => i.district.code === evidenceDistrict) ?? top

  const districtNames = useMemo(() => {
    const map = new Map<string, string>()
    for (const item of items) map.set(item.district.code, item.district.name)
    return map
  }, [items])

  const history = useMemo(() => historyQuery.data?.data ?? [], [historyQuery.data])
  const series = useMemo(() => {
    const latest = new Map<string, SkillHistoryPoint>()
    for (const point of history) {
      const current = latest.get(point.district)
      if (!current || point.quarter > current.quarter) latest.set(point.district, point)
    }
    return [...latest.values()]
      .sort((a, b) => b.score - a.score)
      .map((p) => ({
        key: p.district,
        label: districtNames.get(p.district) ?? districtName(p.district),
      }))
  }, [history, districtNames])

  const demandColumns: Column<SkillDemand>[] = [
    {
      key: 'district',
      header: 'District',
      sortValue: (r) => r.district.name,
      cell: (r) => (
        <Link
          to={`/districts/${r.district.code}`}
          className="rounded font-medium text-foreground hover:text-primary hover:underline focus-visible:outline-2"
        >
          {r.district.name}
        </Link>
      ),
    },
    {
      key: 'score',
      header: 'Demand score',
      sortValue: (r) => r.demand_score,
      cell: (r) => (
        <div className="flex items-center gap-2.5">
          <span className="tabular w-9 text-right font-semibold">{fmtScore(r.demand_score)}</span>
          <div className="h-1.5 w-20 overflow-hidden rounded-full bg-muted" aria-hidden>
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${Math.min(100, r.demand_score)}%` }}
            />
          </div>
        </div>
      ),
    },
    {
      key: 'mentions',
      header: 'Job-ad mentions',
      align: 'right',
      sortValue: (r) => r.mention_count,
      cell: (r) => fmtInt(r.mention_count),
    },
    {
      key: 'trend',
      header: 'Trend',
      cell: (r) => <TrendBadge trend={r.trend_status} />,
    },
    {
      key: 'confidence',
      header: 'Confidence',
      cell: (r) => <ConfidenceBadge confidence={r.confidence} />,
    },
  ]

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Skill demand"
        title={name}
        badges={
          <>
            {known && <Pill tone="primary">{sectorLabel(skillSector(code))}</Pill>}
            {top && <TrendBadge trend={top.trend_status} />}
            <DataSourceBadge source={detailQuery.data?.source} note={detailQuery.data?.note} />
          </>
        }
        description={
          <>
            Demand score (0 to 100) and job-ad mentions per district
            {quarter ? ` for ${quarter}` : ''}, from the analytics engine over the synthetic demo
            world, plus where the skill is taught in the demo course catalogue.
          </>
        }
        actions={
          <Button asChild variant="outline" size="lg">
            <Link to="/skills">
              <ArrowLeft aria-hidden /> All skills
            </Link>
          </Button>
        }
      />

      <QueryState
        query={detailQuery}
        loadingRows={6}
        isEmpty={(r) => r.data.items.length === 0}
        empty={
          <EmptyState
            title="No demand data for this skill"
            description={`The analytics run has no demand rows for "${code}"${quarter ? ` in ${quarter}` : ''}.`}
            action={
              <Button asChild variant="outline" size="sm">
                <Link to="/skills">Back to all skills</Link>
              </Button>
            }
          />
        }
      >
        {(detail) =>
          top && (
            <div className="space-y-6">
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <MetricCard
                  label="Highest demand"
                  value={fmtScore(top.demand_score)}
                  hint={`${top.district.name} · demand score out of 100`}
                  icon={<MapPin aria-hidden />}
                />
                <MetricCard
                  label="Job-ad mentions"
                  value={fmtInt(items.reduce((sum, i) => sum + i.mention_count, 0))}
                  hint={`${quarter ?? 'Latest quarter'} · across ${items.length} district${items.length === 1 ? '' : 's'}`}
                  icon={<Newspaper aria-hidden />}
                  tone="info"
                />
                <MetricCard
                  label="Districts where emerging"
                  value={`${emergingIn.length} of ${items.length}`}
                  hint={
                    emergingIn.length
                      ? emergingIn.map((i) => i.district.name).join(', ')
                      : 'Not emerging in any district'
                  }
                  icon={<Sparkles aria-hidden />}
                  tone={emergingIn.length ? 'primary' : 'success'}
                />
                <MetricCard
                  label="Confidence"
                  value={titleCase(top.confidence)}
                  hint={`For ${top.district.name}: how much evidence is behind the score`}
                  icon={<ShieldCheck aria-hidden />}
                  tone={
                    top.confidence === 'HIGH'
                      ? 'success'
                      : top.confidence === 'MEDIUM'
                        ? 'info'
                        : 'warning'
                  }
                />
              </div>

              <div className="grid gap-6 xl:grid-cols-5">
                <Panel
                  title="Demand by district"
                  description="Highest demand first. Select a district name to open it."
                  actions={<DataSourceBadge source={detail.source} note={detail.note} />}
                  className="animate-in-up xl:col-span-3"
                >
                  <DataTable
                    rows={items}
                    columns={demandColumns}
                    rowKey={(r) => r.district.code}
                    caption={`${name}: demand score, job-ad mentions, trend and confidence by district`}
                    initialSort={{ key: 'score', desc: true }}
                    dense
                  />
                </Panel>

                <WhereTaught code={code} name={name} items={items} className="xl:col-span-2" />
              </div>

              <div className="grid gap-6 xl:grid-cols-5">
                <Panel
                  title="Trend over quarters"
                  description="One line per district, from the analytics engine's quarterly runs."
                  actions={
                    <DataSourceBadge
                      source={historyQuery.data?.source}
                      note={historyQuery.data?.note}
                    />
                  }
                  className="animate-in-up xl:col-span-3"
                >
                  <Tabs
                    value={metric}
                    onValueChange={(v) => setMetric(v as Metric)}
                    className="gap-4"
                  >
                    <TabsList aria-label="Chart measure">
                      <TabsTrigger value="score" className="px-3">
                        Demand score
                      </TabsTrigger>
                      <TabsTrigger value="mentions" className="px-3">
                        Job-ad mentions
                      </TabsTrigger>
                    </TabsList>
                    <QueryState
                      query={historyQuery}
                      loadingRows={5}
                      isEmpty={(r) => r.data.length === 0}
                      empty={<EmptyState title="No quarterly history for this skill" />}
                    >
                      {() => (
                        <>
                          <TabsContent value="score">
                            <DemandChart data={pivot(history, 'score')} series={series} />
                          </TabsContent>
                          <TabsContent value="mentions">
                            <DemandChart
                              data={pivot(history, 'mentions')}
                              series={series}
                              domain={[0, 'auto']}
                              yLabel="Job-ad mentions"
                            />
                          </TabsContent>
                        </>
                      )}
                    </QueryState>
                  </Tabs>
                </Panel>

                <div className="space-y-4 xl:col-span-2">
                  {items.length > 1 && (
                    <div
                      role="group"
                      aria-label="Show evidence for district"
                      className="flex flex-wrap items-center gap-1.5"
                    >
                      <span className="mr-1 text-xs font-medium text-muted-foreground">
                        Evidence for
                      </span>
                      {items.map((item) => {
                        const active = item.district.code === evidenceItem?.district.code
                        return (
                          <Button
                            key={item.district.code}
                            size="sm"
                            variant={active ? 'secondary' : 'ghost'}
                            aria-pressed={active}
                            onClick={() => setEvidenceDistrict(item.district.code)}
                          >
                            {item.district.name}
                          </Button>
                        )
                      })}
                    </div>
                  )}
                  {evidenceItem && (
                    <>
                      <EvidenceCard
                        title={`Why this matters: ${evidenceItem.district.name}`}
                        items={evidenceItem.reasons.map(reasonToEvidence)}
                        className="animate-in-up"
                      />
                      <AssumptionsTable assumptions={evidenceItem.assumptions} />
                    </>
                  )}
                </div>
              </div>
            </div>
          )
        }
      </QueryState>
    </div>
  )
}

// ---------------------------------------------------------------- assumptions
function AssumptionsTable({ assumptions }: { assumptions: Assumption[] }) {
  if (assumptions.length === 0) return null
  return (
    <details className="group rounded-xl border bg-card shadow-xs">
      <summary className="flex cursor-pointer items-center justify-between gap-2 rounded-xl px-5 py-3.5 text-sm font-semibold focus-visible:outline-2">
        Model assumptions ({assumptions.length})
        <span className="text-xs font-normal text-muted-foreground group-open:hidden">Show</span>
        <span className="hidden text-xs font-normal text-muted-foreground group-open:inline">
          Hide
        </span>
      </summary>
      <div className="overflow-x-auto border-t">
        <table className="w-full text-left text-xs">
          <caption className="sr-only">Assumptions used to compute the demand score</caption>
          <thead className="bg-muted/60 text-muted-foreground">
            <tr>
              <th scope="col" className="px-4 py-2 font-semibold">
                Assumption
              </th>
              <th scope="col" className="px-4 py-2 font-semibold">
                Value
              </th>
              <th scope="col" className="px-4 py-2 font-semibold">
                Source
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {assumptions.map((a) => (
              <tr key={a.name} className="align-top">
                <th scope="row" className="px-4 py-2.5 font-medium">
                  {a.name}
                </th>
                <td className="px-4 py-2.5">
                  {formatValue(a.value)}
                  {a.effective && (
                    <span className="block text-muted-foreground">
                      effective: {formatValue(a.effective)}
                    </span>
                  )}
                  {a.note && <span className="block text-muted-foreground">{a.note}</span>}
                </td>
                <td className="px-4 py-2.5 break-words text-muted-foreground">{a.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

// ---------------------------------------------------------------- where it is taught
function WhereTaught({
  code,
  name,
  items,
  className,
}: {
  code: string
  name: string
  items: SkillDemand[]
  className?: string
}) {
  const courses = useMemo(() => coursesTeaching(code), [code])
  const groups = useMemo(() => {
    const districts: DistrictRef[] = items.map((i) => i.district)
    for (const course of courses) {
      if (!districts.some((d) => d.code === course.district.code)) districts.push(course.district)
    }
    return districts.map((district) => ({
      district,
      demand: items.find((i) => i.district.code === district.code),
      courses: courses.filter((c) => c.district.code === district.code),
    }))
  }, [items, courses])
  const emergingGaps = groups.filter(
    (g) => g.courses.length === 0 && g.demand?.trend_status === 'EMERGING',
  )

  return (
    <Panel
      title="Where it is taught"
      description="Demo courses whose syllabus covers this skill, by district."
      actions={<DataSourceBadge source="demo" note={CATALOGUE_NOTE} />}
      className={cn('animate-in-up', className)}
    >
      <div className="space-y-4">
        {courses.length === 0 ? (
          <Callout tone="warning" title="No demo course teaches this skill yet">
            None of the demo courses in the catalogue covers {name}.
          </Callout>
        ) : (
          emergingGaps.length > 0 && (
            <Callout tone="warning" title="Taught away from where demand is emerging">
              {name} is emerging in {emergingGaps.map((g) => g.district.name).join(', ')}, but no
              demo course there teaches it.
            </Callout>
          )
        )}

        <ul className="space-y-3">
          {groups.map((group) => (
            <li key={group.district.code} className="rounded-lg border px-3.5 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold">{group.district.name}</p>
                {group.demand && (
                  <span className="tabular text-xs text-muted-foreground">
                    Demand {fmtScore(group.demand.demand_score)}
                  </span>
                )}
              </div>
              {group.courses.length > 0 ? (
                <ul className="mt-2 space-y-1.5">
                  {group.courses.map((course) => (
                    <CourseLine key={course.id} course={course} />
                  ))}
                </ul>
              ) : (
                <NotTaught district={group.district.name} demand={group.demand} />
              )}
            </li>
          ))}
        </ul>

        <Button asChild variant="outline" size="lg" className="w-full">
          <Link to="/courses">
            <GraduationCap aria-hidden /> See course health for all demo courses
            <ArrowRight aria-hidden />
          </Link>
        </Button>
      </div>
    </Panel>
  )
}

function CourseLine({ course }: { course: TaughtCourse }) {
  return (
    <li>
      <Link
        to={`/courses/${course.id}`}
        className="flex items-start justify-between gap-2 rounded-md px-2 py-1.5 hover:bg-muted focus-visible:outline-2"
      >
        <span className="flex min-w-0 items-start gap-2">
          <BookOpen className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
          <span className="min-w-0">
            <span className="block text-sm font-medium">{course.name}</span>
            <span className="block text-xs text-muted-foreground">{course.institute}</span>
          </span>
        </span>
        <Pill tone={bandTone(course.band)} title="Deepest level at which the syllabus covers it">
          {bandLabel(course.band)}
        </Pill>
      </Link>
    </li>
  )
}

function NotTaught({ district, demand }: { district: string; demand: SkillDemand | undefined }) {
  const emerging = demand?.trend_status === 'EMERGING'
  const high = (demand?.demand_score ?? 0) >= 70
  const medium = (demand?.demand_score ?? 0) >= 45
  const tone: Tone = emerging || high ? 'danger' : medium ? 'warning' : 'neutral'
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      <Pill tone={tone}>Not taught in {district}</Pill>
      {demand && <TrendBadge trend={demand.trend_status} />}
      <span className="text-xs text-muted-foreground">
        {emerging || high
          ? 'Demand is here but no local demo course covers it.'
          : medium
            ? 'Moderate demand, no local demo course.'
            : 'Low demand, no local demo course.'}
      </span>
    </div>
  )
}
