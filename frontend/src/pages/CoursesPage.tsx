// Course Health: how well each demo course matches its district's skill demand. The catalogue
// is demo data; the health score is a demo heuristic computed in the browser
// (src/lib/demo/courseHealth.ts) from skill demand served by the analytics API when reachable.
import {
  BookOpen,
  CircleAlert,
  CircleCheck,
  LayoutGrid,
  Table2,
  TriangleAlert,
  UserCheck,
} from 'lucide-react'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { useFilters } from '@/app/filters'
import type { Column } from '@/components/DataTable'
import { DataTable } from '@/components/DataTable'
import { DataSourceBadge, StatusBadge } from '@/components/badges'
import { Callout, CourseHealthCard, MetricCard } from '@/components/cards'
import { FilterBar } from '@/components/FilterBar'
import { PageHeader, Panel } from '@/components/headers'
import { EmptyState, QueryState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useCourses } from '@/lib/api/queries'
import type { Course, CourseHealthStatus } from '@/lib/api/types'
import { DISTRICTS } from '@/lib/demo/catalog'
import { fmtInt, fmtPct, SECTOR_LABELS, sectorLabel } from '@/lib/format'

type View = 'cards' | 'table'

const STATUS_OPTIONS: { value: 'ALL' | CourseHealthStatus; label: string }[] = [
  { value: 'ALL', label: 'All statuses' },
  { value: 'AT_RISK', label: 'At risk' },
  { value: 'WATCH', label: 'Watch' },
  { value: 'HEALTHY', label: 'Healthy' },
]

const DISTRICT_OPTIONS = [
  { value: 'ALL', label: 'All districts' },
  ...DISTRICTS.map((d) => ({ value: d.code, label: d.name })),
]

const SECTOR_OPTIONS = [
  { value: 'ALL', label: 'All sectors' },
  ...Object.entries(SECTOR_LABELS).map(([value, label]) => ({ value, label })),
]

function pick(options: { value: string }[], value: string): string {
  return options.some((o) => o.value === value) ? value : 'ALL'
}

const byHealth = (a: Course, b: Course) => a.health_score - b.health_score

export default function CoursesPage() {
  const { t } = useTranslation()
  const filters = useFilters()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const query = useCourses()

  const search = params.get('q') ?? ''
  const district = pick(DISTRICT_OPTIONS, params.get('district') ?? filters.district)
  const sector = pick(SECTOR_OPTIONS, params.get('sector') ?? filters.sector)
  const status = pick(STATUS_OPTIONS, params.get('status') ?? 'ALL')
  const view: View = params.get('view') === 'table' ? 'table' : 'cards'
  const filtered = ['q', 'district', 'sector', 'status'].some((key) => params.has(key))

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

  function reset() {
    setParams(
      (prev) => {
        const next = new URLSearchParams()
        const keep = prev.get('view')
        if (keep) next.set('view', keep)
        return next
      },
      { replace: true },
    )
  }

  const courses = useMemo(() => query.data?.data ?? [], [query.data])
  const scoped = useMemo(
    () =>
      courses.filter(
        (c) =>
          (district === 'ALL' || c.district.code === district) &&
          (sector === 'ALL' || c.sector === sector),
      ),
    [courses, district, sector],
  )
  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return scoped
      .filter(
        (c) =>
          (status === 'ALL' || c.health_status === status) &&
          (!needle ||
            c.name.toLowerCase().includes(needle) ||
            c.institute.name.toLowerCase().includes(needle) ||
            c.code.toLowerCase().includes(needle)),
      )
      .sort(byHealth)
  }, [scoped, search, status])

  const count = (s: CourseHealthStatus) => scoped.filter((c) => c.health_status === s).length
  const avgPlacement = scoped.length
    ? scoped.reduce((sum, c) => sum + c.placement_rate, 0) / scoped.length
    : null
  const scopeText = [
    district === 'ALL'
      ? 'All districts'
      : DISTRICT_OPTIONS.find((o) => o.value === district)?.label,
    sector === 'ALL' ? 'all sectors' : sectorLabel(sector),
  ].join(' · ')

  const columns: Column<Course>[] = [
    {
      key: 'name',
      header: 'Course',
      sortValue: (c) => c.name,
      cell: (c) => (
        <div className="min-w-52">
          <p className="font-medium">{c.name}</p>
          <p className="text-xs text-muted-foreground">
            {sectorLabel(c.sector)} · {fmtInt(c.duration_hours)} h
          </p>
        </div>
      ),
    },
    {
      key: 'institute',
      header: 'Institute',
      sortValue: (c) => c.institute.name,
      cell: (c) => <span className="text-sm">{c.institute.name}</span>,
    },
    {
      key: 'district',
      header: 'District',
      sortValue: (c) => c.district.name,
      cell: (c) => c.district.name,
    },
    {
      key: 'health',
      header: 'Health',
      sortValue: (c) => c.health_score,
      cell: (c) => (
        <div className="flex items-center gap-2">
          <span className="tabular w-12 font-semibold">
            {c.health_score}
            <span className="text-xs font-normal text-muted-foreground">/100</span>
          </span>
          <StatusBadge status={c.health_status} />
        </div>
      ),
    },
    {
      key: 'placement',
      header: 'Placement',
      align: 'right',
      sortValue: (c) => c.placement_rate,
      cell: (c) => fmtPct(c.placement_rate),
    },
    {
      key: 'seats',
      header: 'Seats filled',
      align: 'right',
      sortValue: (c) => (c.seats ? c.seats_filled / c.seats : 0),
      cell: (c) => (
        <>
          {fmtInt(c.seats_filled)}
          <span className="text-muted-foreground"> / {fmtInt(c.seats)}</span>
        </>
      ),
    },
    {
      key: 'missing',
      header: 'Missing skills',
      align: 'right',
      sortValue: (c) => c.missing_skills.length,
      cell: (c) =>
        c.missing_skills.length ? (
          <span
            className="font-semibold text-danger"
            title={c.missing_skills.map((m) => m.skill.name).join(', ')}
          >
            {c.missing_skills.length}
          </span>
        ) : (
          <span className="text-muted-foreground">0</span>
        ),
    },
  ]

  const sourceBadge = <DataSourceBadge source={query.data?.source} note={query.data?.note} />
  const empty = (
    <EmptyState
      title="No courses match these filters"
      action={
        <Button variant="outline" size="sm" onClick={reset}>
          Reset filters
        </Button>
      }
    />
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('pages.courses')}
        eyebrow="Demo course catalogue"
        description="How well each demo course matches what its district's employers ask for, with placement and seat use. Lowest health first, so courses that need attention come to the top."
        badges={sourceBadge}
      />

      <Callout tone="demo" title="How course health is scored">
        Course health = 0.35 demand alignment + 0.25 emerging-skill coverage + 0.25 placement rate +
        0.15 curriculum freshness (a demo heuristic, computed in the browser). Healthy is 70 or
        more, Watch 50 to 69, At risk below 50. It is not an official rating.
      </Callout>

      <Tabs
        value={view}
        onValueChange={(v) => setParam('view', v === 'table' ? 'table' : '')}
        className="gap-6"
      >
        <FilterBar
          search={search}
          onSearch={(value) => setParam('q', value)}
          searchLabel="Search course or institute"
          selects={[
            {
              id: 'courses-district',
              label: 'District',
              value: district,
              options: DISTRICT_OPTIONS,
              onChange: (value) => setParam('district', value),
            },
            {
              id: 'courses-status',
              label: 'Health status',
              value: status,
              options: STATUS_OPTIONS,
              onChange: (value) => setParam('status', value === 'ALL' ? '' : value),
            },
            {
              id: 'courses-sector',
              label: 'Sector',
              value: sector,
              options: SECTOR_OPTIONS,
              onChange: (value) => setParam('sector', value),
            },
          ]}
          onReset={filtered ? reset : undefined}
        >
          <div className="flex flex-col gap-1">
            <span id="courses-view-label" className="text-xs font-medium text-muted-foreground">
              View
            </span>
            <TabsList
              aria-labelledby="courses-view-label"
              className="group-data-horizontal/tabs:h-9"
            >
              <TabsTrigger value="cards" className="px-3">
                <LayoutGrid aria-hidden /> Cards
              </TabsTrigger>
              <TabsTrigger value="table" className="px-3">
                <Table2 aria-hidden /> Table
              </TabsTrigger>
            </TabsList>
          </div>
        </FilterBar>

        <QueryState
          query={query}
          loadingRows={6}
          isEmpty={(r) => r.data.length === 0}
          empty={<EmptyState title="No demo courses in the catalogue" />}
        >
          {() => (
            <div className="space-y-6">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-5">
                <MetricCard
                  label="Courses"
                  value={fmtInt(scoped.length)}
                  hint={scopeText}
                  icon={<BookOpen aria-hidden />}
                />
                <MetricCard
                  label="At risk"
                  value={fmtInt(count('AT_RISK'))}
                  hint="Health below 50"
                  icon={<CircleAlert aria-hidden />}
                  tone="danger"
                />
                <MetricCard
                  label="Watch"
                  value={fmtInt(count('WATCH'))}
                  hint="Health 50 to 69"
                  icon={<TriangleAlert aria-hidden />}
                  tone="warning"
                />
                <MetricCard
                  label="Healthy"
                  value={fmtInt(count('HEALTHY'))}
                  hint="Health 70 or more"
                  icon={<CircleCheck aria-hidden />}
                  tone="success"
                />
                <MetricCard
                  label="Average placement rate"
                  value={fmtPct(avgPlacement)}
                  hint="Placed / completed, 2025-26 (synthetic)"
                  icon={<UserCheck aria-hidden />}
                  tone="info"
                />
              </div>

              <Panel
                title="Courses"
                description={
                  <>
                    {visible.length} of {scoped.length} courses, lowest health first.
                    {status !== 'ALL' && (
                      <>
                        {' '}
                        Status: <StatusBadge status={status} className="ml-0.5 align-middle" />
                      </>
                    )}
                  </>
                }
                actions={sourceBadge}
              >
                <TabsContent value="cards">
                  {visible.length === 0 ? (
                    empty
                  ) : (
                    <ul className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
                      {visible.map((course) => (
                        <li key={course.id} className="flex [&>a]:min-w-0 [&>a]:flex-1">
                          <CourseHealthCard course={course} />
                        </li>
                      ))}
                    </ul>
                  )}
                </TabsContent>
                <TabsContent value="table">
                  <DataTable
                    rows={visible}
                    columns={columns}
                    rowKey={(c) => c.id}
                    caption="Demo courses with health score, placement rate, seats filled and missing skills"
                    initialSort={{ key: 'health', desc: false }}
                    onRowClick={(c) => navigate(`/courses/${c.id}`)}
                    empty={empty}
                  />
                </TabsContent>
              </Panel>
            </div>
          )}
        </QueryState>
      </Tabs>
    </div>
  )
}
