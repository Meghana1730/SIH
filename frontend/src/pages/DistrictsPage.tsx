// District Intelligence: compares trained supply with estimated openings (a model estimate)
// across the four demo districts. Every figure comes from the synthetic demo world.
import { ArrowRight } from 'lucide-react'
import { useMemo, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { useFilters } from '@/app/filters'
import { DataSourceBadge, Pill, StatusBadge } from '@/components/badges'
import { DistrictCard } from '@/components/cards'
import { PageHeader, Panel, SectionHeader } from '@/components/headers'
import { MaharashtraMap } from '@/components/MaharashtraMap'
import { EmptyState, ErrorState, LoadingState, QueryState } from '@/components/states'
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useDistrictMismatches, useDistricts, useMismatch } from '@/lib/api/queries'
import type {
  DistrictMismatch,
  DistrictRef,
  MismatchStatus,
  RoleMismatch,
  RoleRef,
} from '@/lib/api/types'
import { ROLES } from '@/lib/demo/catalog'
import { mismatchTone } from '@/lib/evidence'
import { fmtInt, fmtRatio, fmtScore, sectorLabel } from '@/lib/format'
import { cn } from '@/lib/utils'

const TONE_BAR: Record<string, string> = {
  danger: 'bg-danger',
  warning: 'bg-warning',
  success: 'bg-success',
  neutral: 'bg-muted-foreground',
}

const CELL_TINT: Partial<Record<MismatchStatus, string>> = {
  UNDER_SUPPLIED: 'bg-danger-soft/70',
  OVER_SUPPLIED: 'bg-warning-soft/70',
  BALANCED: 'bg-success-soft/70',
}

type Thresholds = { under: number; over: number }

/** The shortage role with the most estimated openings not met by trained supply. */
function topShortage(items: RoleMismatch[], district: string) {
  let best: RoleMismatch | null = null
  for (const item of items) {
    if (item.district.code !== district || item.status !== 'UNDER_SUPPLIED') continue
    if (!best || item.estimated_openings - item.supply > best.estimated_openings - best.supply) {
      best = item
    }
  }
  return best
    ? { title: best.role.title, openings: best.estimated_openings, supply: best.supply }
    : null
}

/** Status thresholds as reported by the analytics engine (scoring config), if present. */
function thresholdsOf(items: RoleMismatch[]): Thresholds | null {
  for (const item of items) {
    const found = item.assumptions.find((a) => a.name === 'status thresholds')
    const value = found?.value as
      { under_supplied_below?: number; over_supplied_above?: number } | undefined
    if (
      typeof value?.under_supplied_below === 'number' &&
      typeof value.over_supplied_above === 'number'
    ) {
      return { under: value.under_supplied_below, over: value.over_supplied_above }
    }
  }
  return null
}

function byScore(a: DistrictMismatch, b: DistrictMismatch) {
  return (b.mismatch_score ?? -1) - (a.mismatch_score ?? -1)
}

export default function DistrictsPage() {
  const { t } = useTranslation()
  const filters = useFilters()
  const districtsQuery = useDistricts()
  const codes = useMemo(
    () => (districtsQuery.data?.data ?? []).map((d) => d.code),
    [districtsQuery.data],
  )
  const summariesQuery = useDistrictMismatches(codes, filters.api.quarter)
  // A comparison page: always all districts. The top-bar district is highlighted instead.
  const mismatchQuery = useMismatch({ sector: filters.api.sector, quarter: filters.api.quarter })

  const mismatchItems = useMemo(
    () =>
      (mismatchQuery.data?.data.items ?? []).filter(
        (m) => filters.sector === 'ALL' || m.role.sector === filters.sector,
      ),
    [mismatchQuery.data, filters.sector],
  )
  const selected = filters.district === 'ALL' ? null : filters.district
  const sectorNote = filters.sector === 'ALL' ? null : sectorLabel(filters.sector)

  /** Loading / error / empty for the per-district summaries (two chained queries). */
  function summaries(render: (data: DistrictMismatch[]) => ReactNode, rows = 4) {
    if (districtsQuery.isError) {
      return <ErrorState error={districtsQuery.error} onRetry={() => districtsQuery.refetch()} />
    }
    if (districtsQuery.isPending) return <LoadingState rows={rows} />
    if (codes.length === 0) {
      return <EmptyState title="No districts" description="The API returned no districts." />
    }
    return (
      <QueryState
        query={summariesQuery}
        loadingRows={rows}
        isEmpty={(r) => r.data.length === 0}
        empty={<EmptyState title="No district summaries for this quarter" />}
      >
        {(result) => render([...result.data].sort(byScore))}
      </QueryState>
    )
  }

  const summariesBadge = (
    <DataSourceBadge source={summariesQuery.data?.source} note={summariesQuery.data?.note} />
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('pages.districts')}
        eyebrow="Supply vs estimated openings"
        description="Compare training supply (people trained per year) with estimated openings (a model estimate from job postings) across the four demo districts. Pick a district to see its roles, courses and evidence."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel
          title="District skill pressure"
          description="Circle size and colour show the mismatch score; select a district to open it."
          actions={summariesBadge}
          className="animate-in-up"
        >
          {summaries((data) => (
            <MaharashtraMap districts={data} />
          ))}
        </Panel>

        <Panel
          title="Ranked by mismatch"
          description="Highest mismatch first. 0 means trained supply matches estimated openings."
          actions={summariesBadge}
          className="animate-in-up"
        >
          {summaries((data) => (
            <DistrictRanking summaries={data} selected={selected} />
          ))}
        </Panel>
      </div>

      <section aria-labelledby="district-cards" className="space-y-4">
        <SectionHeader
          id="district-cards"
          title="District summaries"
          description={
            <>
              Largest gap = the shortage role with the most estimated openings not met by trained
              supply
              {sectorNote ? ` (within ${sectorNote}, from the top-bar sector filter)` : ''}.
            </>
          }
          actions={
            <DataSourceBadge source={mismatchQuery.data?.source} note={mismatchQuery.data?.note} />
          }
        />
        {summaries(
          (data) => (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {data.map((summary) => (
                <div
                  key={summary.district.code}
                  className={cn(
                    'flex rounded-xl [&>a]:flex-1',
                    summary.district.code === selected && 'ring-2 ring-primary/50',
                  )}
                >
                  <DistrictCard
                    summary={summary}
                    topShortage={
                      mismatchQuery.isSuccess
                        ? topShortage(mismatchItems, summary.district.code)
                        : undefined
                    }
                  />
                </div>
              ))}
            </div>
          ),
          2,
        )}
      </section>

      <Panel
        title="Role × district matrix"
        description={
          <>
            Each cell: R = trained supply per year ÷ estimated openings per year (model estimate),
            with its status and the two numbers behind it.
            {sectorNote && (
              <>
                {' '}
                Showing <span className="font-medium text-foreground">{sectorNote}</span> roles
                (top-bar filter).
              </>
            )}
          </>
        }
        actions={
          <DataSourceBadge source={mismatchQuery.data?.source} note={mismatchQuery.data?.note} />
        }
        className="animate-in-up"
      >
        <QueryState
          query={mismatchQuery}
          loadingRows={6}
          isEmpty={() => mismatchItems.length === 0}
          empty={
            <EmptyState
              title="No roles for these filters"
              description="Try another sector or quarter in the top bar."
            />
          }
        >
          {() => (
            <RoleDistrictMatrix
              items={mismatchItems}
              districtOrder={districtsQuery.data?.data ?? []}
              selected={selected}
            />
          )}
        </QueryState>
      </Panel>
    </div>
  )
}

// ---------------------------------------------------------------- ranked list
function DistrictRanking({
  summaries,
  selected,
}: {
  summaries: DistrictMismatch[]
  selected: string | null
}) {
  const max = Math.max(...summaries.map((s) => s.mismatch_score ?? 0), 0.01)
  const definition = summaries.find((s) => s.definition)?.definition
  return (
    <div className="space-y-3">
      <ol className="space-y-2">
        {summaries.map((summary, index) => {
          const tone = mismatchTone(summary.mismatch_score)
          const counts = summary.status_counts
          const isSelected = summary.district.code === selected
          return (
            <li key={summary.district.code}>
              <Link
                to={`/districts/${summary.district.code}`}
                aria-current={isSelected ? 'true' : undefined}
                className={cn(
                  'group flex items-center gap-3 rounded-lg border px-3 py-2.5 transition-colors hover:border-primary/40 hover:bg-muted/40 focus-visible:outline-2',
                  isSelected && 'border-primary/50 bg-accent/60',
                )}
              >
                <span
                  className="grid size-7 shrink-0 place-items-center rounded-full bg-muted text-xs font-semibold text-muted-foreground"
                  aria-hidden
                >
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-medium">
                      {summary.district.name}
                      {isSelected && (
                        <span className="ml-2 text-xs font-normal text-primary">
                          (top-bar district)
                        </span>
                      )}
                    </p>
                    <Pill
                      tone={tone}
                      title="Demand-weighted mean |ln(supply / openings)|; 0 = balanced"
                    >
                      Mismatch {fmtScore(summary.mismatch_score)}
                    </Pill>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
                    <div
                      className={cn('h-full rounded-full', TONE_BAR[tone] ?? TONE_BAR.neutral)}
                      style={{ width: `${((summary.mismatch_score ?? 0) / max) * 100}%` }}
                    />
                  </div>
                  <p className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
                    <span>
                      <span className="tabular font-semibold text-danger">
                        {counts.UNDER_SUPPLIED ?? 0}
                      </span>{' '}
                      shortage
                    </span>
                    <span>
                      <span className="tabular font-semibold text-success">
                        {counts.BALANCED ?? 0}
                      </span>{' '}
                      balanced
                    </span>
                    <span>
                      <span className="tabular font-semibold text-warning">
                        {counts.OVER_SUPPLIED ?? 0}
                      </span>{' '}
                      oversupplied
                    </span>
                    {(counts.INSUFFICIENT_DATA ?? 0) > 0 && (
                      <span>
                        <span className="tabular font-semibold">{counts.INSUFFICIENT_DATA}</span>{' '}
                        insufficient data
                      </span>
                    )}
                  </p>
                </div>
                <ArrowRight
                  className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                  aria-hidden
                />
              </Link>
            </li>
          )
        })}
      </ol>
      {definition && (
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Mismatch score:</span> {definition}. Counts
          are roles by status for the selected quarter.
        </p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- role x district matrix
function RoleDistrictMatrix({
  items,
  districtOrder,
  selected,
}: {
  items: RoleMismatch[]
  districtOrder: DistrictRef[]
  selected: string | null
}) {
  const { districts, roles, cells } = useMemo(() => {
    const cellMap = new Map<string, RoleMismatch>()
    const districtMap = new Map<string, DistrictRef>()
    const roleMap = new Map<string, RoleRef>()
    for (const item of items) {
      cellMap.set(`${item.role.code}|${item.district.code}`, item)
      districtMap.set(item.district.code, item.district)
      roleMap.set(item.role.code, item.role)
    }
    const known = districtOrder.filter((d) => districtMap.has(d.code))
    const extraDistricts = [...districtMap.values()].filter(
      (d) => !known.some((k) => k.code === d.code),
    )
    const orderedRoles = [
      ...ROLES.filter((r) => roleMap.has(r.code)).map((r) => roleMap.get(r.code) ?? r),
      ...[...roleMap.values()].filter((r) => !ROLES.some((k) => k.code === r.code)),
    ]
    return {
      districts: [...known, ...extraDistricts].sort((a, b) => a.name.localeCompare(b.name)),
      roles: orderedRoles,
      cells: cellMap,
    }
  }, [items, districtOrder])
  const thresholds = thresholdsOf(items)

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableCaption className="sr-only">
            Ratio of trained supply to estimated openings for each role (rows) and district
            (columns), with the mismatch status.
          </TableCaption>
          <TableHeader className="bg-muted/60">
            <TableRow className="hover:bg-transparent">
              <TableHead
                scope="col"
                className="w-56 text-xs font-semibold tracking-wide text-muted-foreground uppercase"
              >
                Role
              </TableHead>
              {districts.map((d) => (
                <TableHead
                  key={d.code}
                  scope="col"
                  className={cn('min-w-44', d.code === selected && 'bg-accent')}
                >
                  <Link
                    to={`/districts/${d.code}`}
                    className="inline-flex items-center gap-1 rounded text-sm font-semibold text-foreground hover:text-primary hover:underline focus-visible:outline-2"
                  >
                    {d.name}
                    <ArrowRight className="size-3.5" aria-hidden />
                  </Link>
                  {d.code === selected && (
                    <span className="ml-1.5 text-xs font-normal text-primary">(selected)</span>
                  )}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {roles.map((role) => (
              <TableRow key={role.code} className="hover:bg-transparent">
                <TableHead scope="row" className="h-auto py-3 align-top whitespace-normal">
                  <p className="text-sm font-medium">{role.title}</p>
                  <p className="text-xs font-normal text-muted-foreground">
                    {sectorLabel(role.sector)}
                  </p>
                </TableHead>
                {districts.map((d) => {
                  const cell = cells.get(`${role.code}|${d.code}`)
                  return (
                    <TableCell
                      key={d.code}
                      className={cn(
                        'border-l py-3 align-top',
                        cell && CELL_TINT[cell.status],
                        d.code === selected && 'ring-1 ring-primary/30 ring-inset',
                      )}
                    >
                      {cell ? (
                        <div className="flex flex-col items-start gap-1.5">
                          <div className="flex items-center gap-2">
                            <StatusBadge status={cell.status} />
                            <span className="tabular text-sm font-semibold">
                              <span className="sr-only">Ratio </span>R {fmtRatio(cell.ratio)}
                            </span>
                          </div>
                          <span className="tabular text-xs text-muted-foreground">
                            {fmtInt(cell.supply)}
                            <span className="sr-only"> trained per year</span> / ~
                            {fmtInt(cell.estimated_openings)}
                            <span className="sr-only"> estimated openings per year</span>
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">No data</span>
                      )}
                    </TableCell>
                  )
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <StatusBadge status="UNDER_SUPPLIED" />
          {thresholds ? `R below ${thresholds.under}` : 'Too few trained'}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <StatusBadge status="BALANCED" />
          {thresholds ? `R ${thresholds.under} to ${thresholds.over}` : 'Roughly matched'}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <StatusBadge status="OVER_SUPPLIED" />
          {thresholds ? `R above ${thresholds.over}` : 'More trained than openings'}
        </span>
        <span>
          Small text: trained per year / ~estimated openings per year. Openings are a model estimate
          from job postings, not an official count.
        </span>
      </div>
    </div>
  )
}
