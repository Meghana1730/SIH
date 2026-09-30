import { Check, CheckCircle2, Inbox, MapPin, RotateCcw, Send, TriangleAlert, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'

import { useFilters } from '@/app/filters'
import { ConfidenceBadge, DataSourceBadge, PriorityBadge, StatusBadge } from '@/components/badges'
import { ActionBadge, Callout, EvidenceCard, MetricCard } from '@/components/cards'
import { FilterBar } from '@/components/FilterBar'
import { PageHeader } from '@/components/headers'
import { Drawer } from '@/components/overlays'
import { EmptyState, QueryState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useRecommendations, useSetRecommendationStatus } from '@/lib/api/queries'
import type { Recommendation, RecommendationStatus } from '@/lib/api/types'
import { DISTRICTS } from '@/lib/demo/catalog'
import { cn } from '@/lib/utils'

const TABS: { value: RecommendationStatus | 'ALL'; label: string }[] = [
  { value: 'NEW', label: 'Inbox' },
  { value: 'IN_REVIEW', label: 'Awaiting employers' },
  { value: 'ACCEPTED', label: 'Accepted' },
  { value: 'DISMISSED', label: 'Dismissed' },
  { value: 'ALL', label: 'All' },
]

const ACTION_OPTIONS = [
  { value: 'ALL', label: 'All actions' },
  { value: 'ADD_MODULE', label: 'Add module' },
  { value: 'UPDATE_MODULE', label: 'Update module' },
  { value: 'RETIRE_MODULE', label: 'Shorten module' },
  { value: 'START_COURSE', label: 'Start course' },
  { value: 'INCREASE_SEATS', label: 'Increase seats' },
  { value: 'REDUCE_SEATS', label: 'Reduce seats' },
  { value: 'EMPLOYER_PARTNERSHIP', label: 'Employer partnership' },
]

function PriorityMeter({ score }: { score: number }) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-16 overflow-hidden rounded-full bg-muted" aria-hidden>
        <div
          className={cn(
            'h-full rounded-full',
            score >= 80 ? 'bg-danger' : score >= 65 ? 'bg-warning' : 'bg-muted-foreground',
          )}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="tabular w-6 text-sm font-semibold">{score}</span>
    </div>
  )
}

function Row({ rec, onOpen }: { rec: Recommendation; onOpen: () => void }) {
  return (
    <li>
      <button
        type="button"
        onClick={onOpen}
        className="grid w-full gap-3 px-5 py-4 text-left transition-colors hover:bg-accent/40 focus-visible:outline-2 md:grid-cols-[auto_1fr_auto] md:items-center"
      >
        <PriorityMeter score={rec.priority_score} />
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <ActionBadge action={rec.action} />
            <span className="font-medium">{rec.title}</span>
            {rec.status !== 'NEW' && <StatusBadge status={rec.status} />}
          </div>
          <p className="flex items-center gap-1 truncate text-xs text-muted-foreground">
            <MapPin className="size-3.5 shrink-0" aria-hidden /> {rec.target}
          </p>
        </div>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <CheckCircle2 className="size-3.5 text-success" aria-hidden />{' '}
            {rec.employer_validations}
            <span className="sr-only">employer validations</span>
          </span>
          <ConfidenceBadge confidence={rec.confidence} />
        </div>
      </button>
    </li>
  )
}

function Detail({ rec }: { rec: Recommendation }) {
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <ActionBadge action={rec.action} />
        <PriorityBadge priority={rec.priority} score={rec.priority_score} />
        <StatusBadge status={rec.status} />
        <ConfidenceBadge confidence={rec.confidence} />
      </div>
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <div className="rounded-lg bg-muted p-3">
          <dt className="text-xs text-muted-foreground">Target</dt>
          <dd className="font-medium">{rec.target}</dd>
        </div>
        <div className="rounded-lg bg-muted p-3">
          <dt className="text-xs text-muted-foreground">District</dt>
          <dd className="font-medium">
            <Link to={`/districts/${rec.district.code}`} className="text-primary hover:underline">
              {rec.district.name}
            </Link>
          </dd>
        </div>
      </dl>
      <section>
        <h3 className="text-sm font-semibold">Reason</h3>
        <p className="mt-1 text-sm text-muted-foreground">{rec.reason}</p>
      </section>
      <section>
        <h3 className="text-sm font-semibold">Expected impact</h3>
        <p className="mt-1 text-sm text-muted-foreground">{rec.expected_impact}</p>
      </section>
      <EvidenceCard
        title="Evidence"
        items={rec.evidence.map((e) => ({
          title: e.label,
          detail: e.detail,
          kind: e.kind,
          source: e.source,
        }))}
      />
      <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <CheckCircle2 className="size-4 text-success" aria-hidden />
        {rec.employer_validations} employer validation{rec.employer_validations === 1 ? '' : 's'} so
        far
      </p>
      {rec.course_id && (
        <Button variant="outline" size="sm" asChild>
          <Link to={`/courses/${rec.course_id}`}>Open the course</Link>
        </Button>
      )}
      <Callout tone="demo">
        Recommendation text and priority are demo data written from the analytics results; the
        priority score is a demo heuristic. Decisions are saved in this browser only.
      </Callout>
    </div>
  )
}

export default function RecommendationsPage() {
  const { recId } = useParams()
  const navigate = useNavigate()
  const filters = useFilters()
  const recommendations = useRecommendations()
  const setStatus = useSetRecommendationStatus()
  const [tab, setTab] = useState<RecommendationStatus | 'ALL'>('NEW')
  const [search, setSearch] = useState('')
  const [district, setDistrict] = useState(filters.district)
  const [action, setAction] = useState('ALL')
  const [priority, setPriority] = useState('ALL')

  const all = useMemo(() => recommendations.data?.data ?? [], [recommendations.data])
  const visible = all.filter(
    (r) =>
      (tab === 'ALL' || r.status === tab) &&
      (district === 'ALL' || r.district.code === district) &&
      (action === 'ALL' || r.action === action) &&
      (priority === 'ALL' || r.priority === priority) &&
      (!search || `${r.title} ${r.target}`.toLowerCase().includes(search.toLowerCase())),
  )
  const counts = (status: RecommendationStatus) => all.filter((r) => r.status === status).length
  const selected = all.find((r) => r.id === recId) ?? null

  const decide = (rec: Recommendation, status: RecommendationStatus, message: string) =>
    setStatus.mutate({ id: rec.id, status }, { onSuccess: () => toast.success(message) })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Recommendations"
        description="Decision inbox: curriculum and seat changes ranked by priority, each with the evidence behind it."
        badges={
          <DataSourceBadge
            source={recommendations.data?.source}
            note={recommendations.data?.note}
          />
        }
      />

      <section aria-label="Inbox summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Awaiting decision" value={counts('NEW')} icon={<Inbox aria-hidden />} />
        <MetricCard
          label="High priority, undecided"
          value={all.filter((r) => r.priority === 'HIGH' && r.status === 'NEW').length}
          icon={<TriangleAlert aria-hidden />}
          tone="danger"
        />
        <MetricCard
          label="Awaiting employers"
          value={counts('IN_REVIEW')}
          icon={<Send aria-hidden />}
          tone="warning"
        />
        <MetricCard
          label="Accepted"
          value={counts('ACCEPTED')}
          icon={<Check aria-hidden />}
          tone="success"
        />
      </section>

      <FilterBar
        search={search}
        onSearch={setSearch}
        searchLabel="Search recommendations"
        selects={[
          {
            id: 'rec-district',
            label: 'District',
            value: district,
            onChange: setDistrict,
            options: [
              { value: 'ALL', label: 'All districts' },
              ...DISTRICTS.map((d) => ({ value: d.code, label: d.name })),
            ],
          },
          {
            id: 'rec-action',
            label: 'Action',
            value: action,
            onChange: setAction,
            options: ACTION_OPTIONS,
          },
          {
            id: 'rec-priority',
            label: 'Priority',
            value: priority,
            onChange: setPriority,
            options: [
              { value: 'ALL', label: 'All priorities' },
              { value: 'HIGH', label: 'High' },
              { value: 'MEDIUM', label: 'Medium' },
              { value: 'LOW', label: 'Low' },
            ],
          },
        ]}
        onReset={() => {
          setSearch('')
          setDistrict('ALL')
          setAction('ALL')
          setPriority('ALL')
        }}
      />

      <section className="rounded-xl border bg-card shadow-xs" aria-label="Recommendations">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3">
          <Tabs value={tab} onValueChange={(value) => setTab(value as typeof tab)}>
            <TabsList>
              {TABS.map((t) => (
                <TabsTrigger key={t.value} value={t.value}>
                  {t.label}
                  <span className="tabular ml-1 text-xs text-muted-foreground">
                    {t.value === 'ALL' ? all.length : counts(t.value)}
                  </span>
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
          <p className="text-xs text-muted-foreground">Sorted by priority score (0-100)</p>
        </div>
        <QueryState query={recommendations} isEmpty={(d) => d.data.length === 0}>
          {() =>
            visible.length === 0 ? (
              <EmptyState
                className="m-5"
                title="Nothing here"
                description="No recommendations match these filters."
              />
            ) : (
              <ul className="divide-y">
                {visible.map((rec) => (
                  <Row
                    key={rec.id}
                    rec={rec}
                    onOpen={() => navigate(`/recommendations/${rec.id}`)}
                  />
                ))}
              </ul>
            )
          }
        </QueryState>
      </section>

      <Drawer
        open={Boolean(selected)}
        onOpenChange={(open) => !open && navigate('/recommendations')}
        title={selected?.title ?? ''}
        description={
          selected
            ? `Priority ${selected.priority_score}/100 · ${selected.district.name}`
            : undefined
        }
        footer={
          selected && (
            <>
              {selected.status !== 'NEW' && (
                <Button
                  variant="ghost"
                  onClick={() => decide(selected, 'NEW', 'Moved back to the inbox')}
                >
                  <RotateCcw aria-hidden /> Reopen
                </Button>
              )}
              <Button
                variant="ghost"
                disabled={selected.status === 'DISMISSED'}
                onClick={() => decide(selected, 'DISMISSED', 'Recommendation dismissed')}
              >
                <X aria-hidden /> Dismiss
              </Button>
              <Button
                variant="outline"
                disabled={selected.status === 'IN_REVIEW'}
                onClick={() => {
                  decide(selected, 'IN_REVIEW', 'Sent to employers for validation')
                  navigate('/employer', { state: { recommendationId: selected.id } })
                }}
              >
                <Send aria-hidden /> Ask employers to validate
              </Button>
              <Button
                disabled={selected.status === 'ACCEPTED'}
                onClick={() => decide(selected, 'ACCEPTED', `Accepted: ${selected.title}`)}
              >
                <Check aria-hidden /> Accept
              </Button>
            </>
          )
        }
      >
        {selected && <Detail rec={selected} />}
      </Drawer>
    </div>
  )
}
