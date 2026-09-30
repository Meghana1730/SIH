// Skills Demand: one row per skill, combining the per-district demand scores from the
// analytics engine (synthetic demo world). Local filters live in the URL so views can be shared.
import { Layers, Sparkles, TrendingDown, Trophy } from 'lucide-react'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { useFilters } from '@/app/filters'
import type { Column } from '@/components/DataTable'
import { DataTable } from '@/components/DataTable'
import {
  ConfidenceBadge,
  DataSourceBadge,
  Pill,
  SyntheticBadge,
  TrendBadge,
} from '@/components/badges'
import { MetricCard, SkillGapCard } from '@/components/cards'
import { FilterBar } from '@/components/FilterBar'
import { PageHeader, Panel, SectionHeader } from '@/components/headers'
import { EmptyState, QueryState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { useSkills } from '@/lib/api/queries'
import { coursesTeaching, type SkillRow } from '@/lib/api/skillsApi'
import type { Confidence, TrendStatus } from '@/lib/api/types'
import { districtName, fmtInt, fmtScore, SECTOR_LABELS, sectorLabel } from '@/lib/format'

const TREND_OPTIONS = [
  { value: 'ALL', label: 'All trends' },
  { value: 'EMERGING', label: 'Emerging' },
  { value: 'GROWING', label: 'Growing' },
  { value: 'STABLE', label: 'Stable' },
  { value: 'DECLINING', label: 'Declining' },
]

const SECTOR_OPTIONS = [
  { value: 'ALL', label: 'All sectors' },
  ...Object.entries(SECTOR_LABELS).map(([value, label]) => ({ value, label })),
]

const TREND_RANK: Record<TrendStatus, number> = {
  EMERGING: 4,
  GROWING: 3,
  STABLE: 2,
  DECLINING: 1,
  INSUFFICIENT_DATA: 0,
}

const CONFIDENCE_RANK: Record<Confidence, number> = { HIGH: 3, MEDIUM: 2, LOW: 1 }

/** Districts where a skill is EMERGING but no demo course in that district teaches it. */
function untaughtEmerging(row: SkillRow): string[] {
  const taughtIn = new Set(coursesTeaching(row.code).map((c) => c.district.code))
  return row.districts
    .filter((d) => d.trend_status === 'EMERGING' && !taughtIn.has(d.district.code))
    .map((d) => d.district.name)
}

export default function SkillsPage() {
  const { t } = useTranslation()
  const filters = useFilters()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const query = useSkills({ district: filters.api.district, quarter: filters.api.quarter })

  const search = params.get('q') ?? ''
  const trend = params.get('trend') ?? 'ALL'
  const sectorParam = params.get('sector') ?? filters.sector
  const sector = SECTOR_OPTIONS.some((o) => o.value === sectorParam) ? sectorParam : 'ALL'

  function setParam(key: string, value: string) {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        if (value) next.set(key, value)
        else next.delete(key)
        return next
      },
      { replace: true },
    )
  }

  const rows = useMemo(() => query.data?.data ?? [], [query.data])
  const scoped = useMemo(
    () => rows.filter((r) => sector === 'ALL' || r.sector === sector),
    [rows, sector],
  )
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return scoped.filter(
      (r) =>
        (trend === 'ALL' || r.trend === trend) &&
        (!needle || r.name.toLowerCase().includes(needle) || r.code.includes(needle)),
    )
  }, [scoped, search, trend])

  const emerging = useMemo(() => scoped.filter((r) => r.trend === 'EMERGING').slice(0, 4), [scoped])
  const quarter = rows[0]?.districts[0]?.quarter
  const scopeText =
    filters.district === 'ALL' ? 'all demo districts' : districtName(filters.district)
  const sectorText = sector === 'ALL' ? 'All sectors' : sectorLabel(sector)
  const top = scoped[0]
  const filtered = search !== '' || trend !== 'ALL' || params.has('sector')

  const columns: Column<SkillRow>[] = [
    {
      key: 'name',
      header: 'Skill',
      sortValue: (r) => r.name,
      cell: (r) => (
        <div className="min-w-44">
          <Link
            to={`/skills/${r.code}`}
            onClick={(event) => event.stopPropagation()}
            className="rounded font-medium text-foreground hover:text-primary hover:underline focus-visible:outline-2"
          >
            {r.name}
          </Link>
          <p className="text-xs text-muted-foreground">{r.code}</p>
        </div>
      ),
    },
    {
      key: 'sector',
      header: 'Sector',
      sortValue: (r) => r.sector,
      cell: (r) => <Pill>{sectorLabel(r.sector)}</Pill>,
    },
    {
      key: 'score',
      header: 'Top demand score',
      sortValue: (r) => r.top_score,
      cell: (r) => (
        <div className="flex items-center gap-2.5">
          <span className="tabular w-9 text-right font-semibold">{fmtScore(r.top_score)}</span>
          <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted" aria-hidden>
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${Math.min(100, r.top_score)}%` }}
            />
          </div>
        </div>
      ),
    },
    {
      key: 'district',
      header: 'Top district',
      sortValue: (r) => r.top_district,
      cell: (r) => r.top_district,
    },
    {
      key: 'mentions',
      header: 'Job-ad mentions',
      align: 'right',
      sortValue: (r) => r.mentions,
      cell: (r) => fmtInt(r.mentions),
    },
    {
      key: 'trend',
      header: 'Trend',
      sortValue: (r) => (r.trend ? TREND_RANK[r.trend] : -1),
      cell: (r) => <TrendBadge trend={r.trend} />,
    },
    {
      key: 'confidence',
      header: 'Confidence',
      sortValue: (r) => {
        const c = r.districts[0]?.confidence
        return c ? CONFIDENCE_RANK[c] : null
      },
      cell: (r) => <ConfidenceBadge confidence={r.districts[0]?.confidence} />,
    },
    {
      key: 'data',
      header: 'Data',
      cell: (r) =>
        r.is_synthetic ? <SyntheticBadge /> : <span className="text-muted-foreground">-</span>,
    },
  ]

  const sourceBadge = <DataSourceBadge source={query.data?.source} note={query.data?.note} />

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('pages.skills')}
        eyebrow="Skill demand by district"
        description={
          <>
            Demand score (0 to 100) per skill from job-ad mentions and employer surveys, for{' '}
            {scopeText}
            {quarter ? `, ${quarter}` : ''}. Each row shows the district where the skill is most in
            demand. Select a skill for its trend, evidence and where it is taught.
          </>
        }
        badges={sourceBadge}
      />

      <FilterBar
        search={search}
        onSearch={(value) => setParam('q', value)}
        searchLabel="Search skills"
        selects={[
          {
            id: 'skills-trend',
            label: 'Trend',
            value: trend,
            options: TREND_OPTIONS,
            onChange: (value) => setParam('trend', value === 'ALL' ? '' : value),
          },
          {
            id: 'skills-sector',
            label: 'Sector',
            value: sector,
            options: SECTOR_OPTIONS,
            onChange: (value) => setParam('sector', value),
          },
        ]}
        onReset={filtered ? () => setParams(new URLSearchParams(), { replace: true }) : undefined}
      />

      <QueryState
        query={query}
        loadingRows={6}
        isEmpty={(r) => r.data.length === 0}
        empty={
          <EmptyState
            title="No skill demand for this quarter"
            description="The analytics run has no skill rows for the selected district and quarter."
          />
        }
      >
        {() => (
          <div className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                label="Skills tracked"
                value={fmtInt(scoped.length)}
                hint={`${sectorText} · ${scopeText}`}
                icon={<Layers aria-hidden />}
              />
              <MetricCard
                label="Emerging skills"
                value={fmtInt(scoped.filter((r) => r.trend === 'EMERGING').length)}
                hint="Emerging in at least one district shown"
                icon={<Sparkles aria-hidden />}
                tone="primary"
              />
              <MetricCard
                label="Declining skills"
                value={fmtInt(scoped.filter((r) => r.trend === 'DECLINING').length)}
                hint="Declining in every district with enough data"
                icon={<TrendingDown aria-hidden />}
                tone="warning"
              />
              <MetricCard
                label="Top skill by demand"
                value={
                  top ? (
                    <Link
                      to={`/skills/${top.code}`}
                      className="block truncate rounded text-xl hover:text-primary hover:underline focus-visible:outline-2"
                      title={top.name}
                    >
                      {top.name}
                    </Link>
                  ) : (
                    '-'
                  )
                }
                hint={
                  top ? `Demand score ${fmtScore(top.top_score)} in ${top.top_district}` : undefined
                }
                icon={<Trophy aria-hidden />}
                tone="success"
              />
            </div>

            <section aria-labelledby="emerging-skills" className="space-y-3">
              <SectionHeader
                id="emerging-skills"
                title="Emerging skills"
                description="Highest-scoring skills whose job-ad mentions are rising fastest. Red text marks districts where the skill is emerging but no demo course there teaches it."
                actions={sourceBadge}
              />
              {emerging.length === 0 ? (
                <EmptyState
                  title="No emerging skills in this view"
                  description="Try all sectors or all districts."
                  className="py-6"
                />
              ) : (
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  {emerging.map((row) => {
                    const gaps = untaughtEmerging(row)
                    return (
                      <SkillGapCard
                        key={row.code}
                        skill={{ code: row.code, name: row.name }}
                        demandScore={row.top_score}
                        trend={row.trend}
                        postings={row.mentions}
                        taught={gaps.length ? `Not taught in ${gaps.join(', ')}` : undefined}
                        href={`/skills/${row.code}`}
                      />
                    )
                  })}
                </div>
              )}
            </section>

            <Panel
              title="All skills"
              description={`${visible.length} of ${scoped.length} skills. Job-ad mentions are summed across the districts shown; confidence is for the top district.`}
              actions={sourceBadge}
            >
              <DataTable
                rows={visible}
                columns={columns}
                rowKey={(r) => r.code}
                caption="Skills by demand score, with top district, job-ad mentions, trend and confidence"
                initialSort={{ key: 'score', desc: true }}
                onRowClick={(r) => navigate(`/skills/${r.code}`)}
                empty={
                  <EmptyState
                    title="No skills match these filters"
                    action={
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setParams(new URLSearchParams(), { replace: true })}
                      >
                        Reset filters
                      </Button>
                    }
                  />
                }
              />
            </Panel>
          </div>
        )}
      </QueryState>
    </div>
  )
}
