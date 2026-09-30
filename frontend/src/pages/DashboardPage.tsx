import {
  ArrowRight,
  Factory,
  GraduationCap,
  Sparkles,
  TrendingDown,
  TriangleAlert,
  Users,
} from 'lucide-react'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { useFilters } from '@/app/filters'
import { ConfidenceBadge, DataSourceBadge, Pill, StatusBadge } from '@/components/badges'
import { Callout, MetricCard, RecommendationCard } from '@/components/cards'
import { DemandChart } from '@/components/charts'
import { DataTable } from '@/components/DataTable'
import { PageHeader, Panel } from '@/components/headers'
import { MaharashtraMap } from '@/components/MaharashtraMap'
import { LoadingState, QueryState } from '@/components/states'
import { Button } from '@/components/ui/button'
import {
  useCourses,
  useDistrictMismatches,
  useDistricts,
  useMismatch,
  useRecommendations,
  useRoleDemand,
  useRoleHistory,
  useSkillDemand,
} from '@/lib/api/queries'
import type { RoleDemand, RoleMismatch, SkillDemand } from '@/lib/api/types'
import { useDemoState } from '@/lib/demo/store'
import { mismatchTone } from '@/lib/evidence'
import { districtName, fmtInt, fmtRatio, fmtScore } from '@/lib/format'
import { cn } from '@/lib/utils'

type Signal = {
  id: string
  kind: 'emerging' | 'event' | 'declining' | 'oversupply'
  text: string
  district: string
  href: string
}

const SIGNAL_STYLE = {
  emerging: { icon: Sparkles, label: 'Emerging skill', className: 'bg-accent text-primary' },
  event: { icon: Factory, label: 'Industry event', className: 'bg-danger-soft text-danger' },
  declining: { icon: TrendingDown, label: 'Declining', className: 'bg-warning-soft text-warning' },
  oversupply: { icon: Users, label: 'Oversupply', className: 'bg-warning-soft text-warning' },
} as const

function marketSignals(
  skills: SkillDemand[],
  roles: RoleDemand[],
  mismatch: RoleMismatch[],
): Signal[] {
  const signals: Signal[] = []
  const seenEvents = new Set<string>()
  for (const role of [...roles].sort((a, b) => b.demand_score - a.demand_score)) {
    for (const reason of role.reasons) {
      const eventId = String(reason.evidence.event_id ?? '')
      if (reason.code !== 'industry_event' || seenEvents.has(eventId)) continue
      seenEvents.add(eventId)
      signals.push({
        id: `event-${eventId}-${role.role.code}`,
        kind: 'event',
        text: reason.text,
        district: role.district.name,
        href: `/districts/${role.district.code}`,
      })
    }
  }
  const emerging = skills
    .filter((s) => s.trend_status === 'EMERGING')
    .sort((a, b) => b.demand_score - a.demand_score)
    .slice(0, 3)
  for (const skill of emerging) {
    const reason = skill.reasons.find((r) => r.code === 'skill_emerging')
    signals.push({
      id: `emerging-${skill.skill.code}-${skill.district.code}`,
      kind: 'emerging',
      text: reason?.text ?? `${skill.skill.name} is emerging in ${skill.district.name} job ads.`,
      district: skill.district.name,
      href: `/skills/${skill.skill.code}`,
    })
  }
  for (const item of mismatch.filter((m) => m.status === 'OVER_SUPPLIED').slice(0, 2)) {
    signals.push({
      id: `over-${item.role.code}-${item.district.code}`,
      kind: 'oversupply',
      text: `${item.role.title} in ${item.district.name}: about ${fmtInt(item.supply)} trained a year vs ~${fmtInt(item.estimated_openings)} estimated openings (ratio ${fmtRatio(item.ratio)}).`,
      district: item.district.name,
      href: `/districts/${item.district.code}`,
    })
  }
  const declining = skills
    .filter((s) => s.trend_status === 'DECLINING')
    .sort((a, b) => a.demand_score - b.demand_score)
  if (declining.length) {
    const names = [...new Set(declining.map((d) => d.skill.name))]
    const where = [...new Set(declining.map((d) => d.district.name))]
    signals.push({
      id: 'declining',
      kind: 'declining',
      text: `${names.join(', ')}: job-ad mentions declining in ${where.length === 4 ? 'all four districts' : where.join(', ')}.`,
      district: where.join(', '),
      href: `/skills/${declining[0].skill.code}`,
    })
  }
  return signals
}

export default function DashboardPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const filters = useFilters()
  const demo = useDemoState()
  const districts = useDistricts()
  const codes = useMemo(() => (districts.data?.data ?? []).map((d) => d.code), [districts.data])
  const districtSummaries = useDistrictMismatches(codes, filters.api.quarter)
  const mismatch = useMismatch(filters.api)
  const roleDemand = useRoleDemand(filters.api)
  const skillDemand = useSkillDemand({
    district: filters.api.district,
    quarter: filters.api.quarter,
  })
  const courses = useCourses()
  const recommendations = useRecommendations()
  const trendDistrict = filters.district === 'ALL' ? 'MH-NASHIK' : filters.district
  const history = useRoleHistory(trendDistrict)

  const items = useMemo(() => mismatch.data?.data.items ?? [], [mismatch.data])
  const shortage = items.filter((m) => m.status === 'UNDER_SUPPLIED')
  const openings = items.reduce((sum, m) => sum + m.estimated_openings, 0)
  const trained = items.reduce((sum, m) => sum + m.supply, 0)
  const emergingSkills = new Set(
    (skillDemand.data?.data.items ?? [])
      .filter((s) => s.trend_status === 'EMERGING')
      .map((s) => s.skill.code),
  )
  const atRisk = (courses.data?.data ?? [])
    .filter((c) => c.health_status === 'AT_RISK')
    .sort((a, b) => a.health_score - b.health_score)
  const quarter = mismatch.data?.data.quarter ?? filters.quarter

  const signals = marketSignals(
    skillDemand.data?.data.items ?? [],
    roleDemand.data?.data.items ?? [],
    items,
  )

  const topGaps = [...shortage]
    .sort((a, b) => b.estimated_openings - b.supply - (a.estimated_openings - a.supply))
    .slice(0, 8)

  const historyRoles = useMemo(() => {
    const points = history.data?.data ?? []
    const latest = points.filter((p) => p.quarter === points[points.length - 1]?.quarter)
    return latest
      .sort((a, b) => b.score - a.score)
      .slice(0, 4)
      .map((p) => p.role)
  }, [history.data])
  const roleTitles = useMemo(() => {
    const titles: Record<string, string> = {}
    for (const r of roleDemand.data?.data.items ?? []) titles[r.role.code] = r.role.title
    for (const m of items) titles[m.role.code] = m.role.title
    return titles
  }, [roleDemand.data, items])
  const chartData = useMemo(() => {
    const byQuarter = new Map<string, Record<string, string | number | null>>()
    for (const p of history.data?.data ?? []) {
      if (!historyRoles.includes(p.role)) continue
      const row = byQuarter.get(p.quarter) ?? { quarter: p.quarter }
      row[p.role] = p.score
      byQuarter.set(p.quarter, row)
    }
    return [...byQuarter.values()]
  }, [history.data, historyRoles])

  const topRecommendations = (recommendations.data?.data ?? [])
    .filter((r) => r.status !== 'DISMISSED')
    .slice(0, 3)

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={`${filters.district === 'ALL' ? t('app.state') : districtName(filters.district)} · ${quarter ?? 'latest quarter'}`}
        title={t('pages.dashboard')}
        description="Where Electrical, EV and Solar PV skills are short or in surplus across the demo districts, why, and what training should change."
        badges={<DataSourceBadge source={mismatch.data?.source} note={mismatch.data?.note} />}
        actions={
          <Button asChild>
            <Link to="/districts/MH-NASHIK">
              Investigate Nashik <ArrowRight aria-hidden />
            </Link>
          </Button>
        }
      />

      {demo.evExpansionSimulated && (
        <Callout
          tone="danger"
          title="Simulated event: Nashik EV expansion"
          icon={<Factory aria-hidden />}
        >
          A simulated EV battery-pack assembly unit in Nashik is expected to add about 180 EV
          Service Technician jobs in 2026Q4-2027Q3 (synthetic event from the demo world).{' '}
          <Link
            to="/districts/MH-NASHIK"
            className="font-medium text-primary underline-offset-2 hover:underline"
          >
            See the Nashik gap
          </Link>
        </Callout>
      )}

      <section aria-label="Key indicators" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {mismatch.isPending ? (
          Array.from({ length: 4 }, (_, i) => <LoadingState key={i} rows={2} />)
        ) : (
          <>
            <MetricCard
              label="Role gaps flagged"
              value={`${shortage.length} / ${items.length}`}
              hint="role × district pairs with supply below 0.7 of estimated openings"
              icon={<TriangleAlert aria-hidden />}
              tone="danger"
            />
            <MetricCard
              label="Estimated openings a year"
              value={fmtInt(openings)}
              hint={`vs ${fmtInt(trained)} trained a year · openings are a model estimate`}
              icon={<Factory aria-hidden />}
              tone="primary"
            />
            <MetricCard
              label="Emerging skills"
              value={emergingSkills.size}
              hint="skills whose job-ad mentions are rising fast"
              icon={<Sparkles aria-hidden />}
              tone="info"
            />
            <MetricCard
              label="Courses at risk"
              value={
                courses.isPending ? '-' : `${atRisk.length} / ${courses.data?.data.length ?? 0}`
              }
              hint="course health below 50 (demo heuristic)"
              icon={<GraduationCap aria-hidden />}
              tone="warning"
              footer={
                atRisk[0] && (
                  <Link
                    to={`/courses/${atRisk[0].id}`}
                    className="text-xs font-medium text-primary hover:underline"
                  >
                    Lowest: {atRisk[0].name.replace(' (demo syllabus)', '')},{' '}
                    {atRisk[0].institute.name} ({atRisk[0].health_score}/100)
                  </Link>
                )
              }
            />
          </>
        )}
      </section>

      <div className="grid gap-6 xl:grid-cols-12">
        <Panel
          className="xl:col-span-7"
          title="District skill pressure"
          description="Mismatch score = demand-weighted mean of |ln(supply ÷ estimated openings)|; 0 is balanced."
          actions={
            <DataSourceBadge
              source={districtSummaries.data?.source}
              note={districtSummaries.data?.note}
            />
          }
        >
          <QueryState query={districtSummaries} isEmpty={(d) => d.data.length === 0}>
            {(result) => (
              <div className="grid gap-6 md:grid-cols-[1.3fr_1fr]">
                <MaharashtraMap districts={result.data} />
                <ol className="space-y-2" aria-label="Districts ranked by mismatch">
                  {[...result.data]
                    .sort((a, b) => (b.mismatch_score ?? 0) - (a.mismatch_score ?? 0))
                    .map((d, index) => (
                      <li key={d.district.code}>
                        <Link
                          to={`/districts/${d.district.code}`}
                          className="flex items-center gap-3 rounded-lg border px-3 py-2.5 transition-colors hover:border-primary/40 hover:bg-accent/40 focus-visible:outline-2"
                        >
                          <span className="tabular w-4 text-sm text-muted-foreground">
                            {index + 1}
                          </span>
                          <span className="flex-1">
                            <span className="block text-sm font-medium">{d.district.name}</span>
                            <span className="block text-xs text-muted-foreground">
                              {d.status_counts.UNDER_SUPPLIED ?? 0} shortage ·{' '}
                              {d.status_counts.OVER_SUPPLIED ?? 0} oversupply ·{' '}
                              {d.status_counts.BALANCED ?? 0} balanced
                            </span>
                          </span>
                          <Pill tone={mismatchTone(d.mismatch_score)}>
                            {fmtScore(d.mismatch_score)}
                          </Pill>
                        </Link>
                      </li>
                    ))}
                </ol>
              </div>
            )}
          </QueryState>
        </Panel>

        <Panel
          className="xl:col-span-5"
          title="Market signals"
          description="Only signals backed by stored evidence."
          actions={
            <DataSourceBadge source={skillDemand.data?.source} note={skillDemand.data?.note} />
          }
          bodyClassName="p-0"
        >
          {skillDemand.isPending || roleDemand.isPending ? (
            <LoadingState className="p-5" />
          ) : (
            <ul className="divide-y">
              {signals.slice(0, 6).map((signal) => {
                const style = SIGNAL_STYLE[signal.kind]
                const Icon = style.icon
                return (
                  <li key={signal.id}>
                    <Link
                      to={signal.href}
                      className="flex gap-3 px-5 py-3.5 transition-colors hover:bg-accent/40 focus-visible:outline-2"
                    >
                      <span
                        className={cn(
                          'grid size-8 shrink-0 place-items-center rounded-lg',
                          style.className,
                        )}
                      >
                        <Icon className="size-4" aria-hidden />
                      </span>
                      <span className="min-w-0 space-y-0.5">
                        <span className="block text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                          {style.label} · {signal.district}
                        </span>
                        <span className="block text-sm">{signal.text}</span>
                      </span>
                    </Link>
                  </li>
                )
              })}
            </ul>
          )}
        </Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-12">
        <Panel
          className="xl:col-span-7"
          title="Largest training gaps"
          description="Roles where trained supply is furthest below estimated openings (model estimate, not an official figure)."
          actions={<DataSourceBadge source={mismatch.data?.source} note={mismatch.data?.note} />}
        >
          <QueryState query={mismatch} isEmpty={(d) => d.data.items.length === 0}>
            {() => (
              <DataTable
                dense
                rows={topGaps}
                rowKey={(r) => `${r.role.code}-${r.district.code}`}
                caption="Largest training gaps"
                onRowClick={(r) => navigate(`/districts/${r.district.code}`)}
                columns={[
                  {
                    key: 'role',
                    header: 'Role',
                    cell: (r) => (
                      <div>
                        <p className="font-medium">{r.role.title}</p>
                        <p className="text-xs text-muted-foreground">{r.district.name}</p>
                      </div>
                    ),
                  },
                  {
                    key: 'demand',
                    header: 'Demand',
                    align: 'right',
                    sortValue: (r) => r.demand_score,
                    cell: (r) => fmtScore(r.demand_score),
                  },
                  {
                    key: 'supply',
                    header: 'Trained / yr',
                    align: 'right',
                    sortValue: (r) => r.supply,
                    cell: (r) => fmtInt(r.supply),
                  },
                  {
                    key: 'openings',
                    header: 'Est. openings / yr',
                    align: 'right',
                    sortValue: (r) => r.estimated_openings,
                    cell: (r) => fmtInt(r.estimated_openings),
                  },
                  {
                    key: 'ratio',
                    header: 'Ratio',
                    align: 'right',
                    sortValue: (r) => r.ratio,
                    cell: (r) => fmtRatio(r.ratio),
                  },
                  {
                    key: 'status',
                    header: 'Status',
                    cell: (r) => <StatusBadge status={r.status} />,
                  },
                  {
                    key: 'conf',
                    header: 'Confidence',
                    cell: (r) => <ConfidenceBadge confidence={r.confidence} />,
                  },
                ]}
              />
            )}
          </QueryState>
        </Panel>

        <Panel
          className="xl:col-span-5"
          title={`Demand trend · ${districtName(trendDistrict)}`}
          description="Demand score (0-100) of the four highest-demand roles by quarter."
          actions={<DataSourceBadge source={history.data?.source} note={history.data?.note} />}
        >
          <QueryState query={history} isEmpty={(d) => d.data.length === 0}>
            {() => (
              <DemandChart
                data={chartData}
                series={historyRoles.map((code) => ({
                  key: code,
                  label: roleTitles[code] ?? code,
                }))}
                height={280}
              />
            )}
          </QueryState>
        </Panel>
      </div>

      <Panel
        title="Priority actions"
        description="Highest-priority recommendations awaiting a decision."
        actions={
          <>
            <DataSourceBadge
              source={recommendations.data?.source}
              note={recommendations.data?.note}
            />
            <Button variant="outline" size="sm" asChild>
              <Link to="/recommendations">
                Open decision inbox <ArrowRight aria-hidden />
              </Link>
            </Button>
          </>
        }
      >
        <QueryState query={recommendations} isEmpty={(d) => d.data.length === 0}>
          {() => (
            <div className="grid gap-4 lg:grid-cols-3">
              {topRecommendations.map((rec) => (
                <RecommendationCard
                  key={rec.id}
                  rec={rec}
                  compact
                  onOpen={() => navigate(`/recommendations/${rec.id}`)}
                />
              ))}
            </div>
          )}
        </QueryState>
      </Panel>
    </div>
  )
}
