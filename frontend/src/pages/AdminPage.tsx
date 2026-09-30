// Demo Controls: run the analytics pipeline, simulate the Nashik EV event, reset demo actions,
// and check system health, data mode, users and the audit log.
import {
  Activity,
  CircleCheck,
  CircleX,
  Cpu,
  Database,
  FlaskConical,
  LoaderCircle,
  Lock,
  Play,
  RefreshCw,
  RotateCcw,
  ScrollText,
  Users,
  Zap,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { ROLE_LABELS, useSession } from '@/app/session'
import { DataSourceBadge, Pill, SyntheticBadge, type Tone } from '@/components/badges'
import { Callout } from '@/components/cards'
import { DataTable, type Column } from '@/components/DataTable'
import { PageHeader, Panel } from '@/components/headers'
import { ConfirmDialog } from '@/components/overlays'
import { EmptyState, QueryState } from '@/components/states'
import { Button } from '@/components/ui/button'
import {
  errorMessage,
  useAuditLog,
  useDbHealth,
  useHealth,
  useResetDemo,
  useRunPipeline,
  useSimulateEvExpansion,
  useUsers,
} from '@/lib/api/queries'
import type { AuditEntry, User } from '@/lib/api/types'
import { DISTRICTS } from '@/lib/demo/catalog'
import { DEMO_FALLBACK_ENABLED } from '@/lib/demo/config'
import { useDemoState } from '@/lib/demo/store'
import { fmtDateTime, fmtInt } from '@/lib/format'
import { cn } from '@/lib/utils'

// ---------------------------------------------------------------- building blocks
function ControlCard({
  icon,
  title,
  status,
  description,
  children,
  footer,
}: {
  icon: ReactNode
  title: string
  status: ReactNode
  description: ReactNode
  children?: ReactNode
  footer: ReactNode
}) {
  return (
    <section className="animate-in-up flex flex-col rounded-xl border bg-card shadow-xs">
      <div className="flex items-start gap-3 border-b px-5 py-4">
        <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-accent text-primary [&_svg]:size-5">
          {icon}
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          <h2 className="font-semibold">{title}</h2>
          <div className="flex flex-wrap gap-1.5">{status}</div>
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-4 p-5">
        <div className="text-sm text-muted-foreground">{description}</div>
        {children}
      </div>
      <div className="flex flex-wrap items-center gap-2 border-t px-5 py-4">{footer}</div>
    </section>
  )
}

function Stat({
  label,
  value,
  mono = false,
  className,
}: {
  label: string
  value: ReactNode
  mono?: boolean
  className?: string
}) {
  return (
    <div className={cn('min-w-0 rounded-lg bg-muted/60 px-3 py-2', className)}>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd
        className={cn(
          'tabular truncate text-sm font-semibold text-foreground',
          mono && 'font-mono text-xs',
        )}
        title={typeof value === 'string' ? value : undefined}
      >
        {value}
      </dd>
    </div>
  )
}

function InfoRow({
  label,
  children,
  hint,
}: {
  label: string
  children: ReactNode
  hint?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 py-3">
      <dt className="text-sm font-medium">{label}</dt>
      <dd className="flex min-w-0 flex-col items-end gap-1 text-right text-sm">
        <div className="flex flex-wrap items-center justify-end gap-2">{children}</div>
        {hint && <p className="max-w-xs text-xs text-muted-foreground">{hint}</p>}
      </dd>
    </div>
  )
}

function Check({ state, children }: { state: 'ok' | 'error' | 'checking'; children: ReactNode }) {
  const tone: Tone = state === 'ok' ? 'success' : state === 'error' ? 'danger' : 'neutral'
  const icon =
    state === 'ok' ? (
      <CircleCheck aria-hidden />
    ) : state === 'error' ? (
      <CircleX aria-hidden />
    ) : (
      <LoaderCircle className="animate-spin" aria-hidden />
    )
  return (
    <Pill tone={tone} icon={icon}>
      {children}
    </Pill>
  )
}

// ---------------------------------------------------------------- table columns
const USER_COLUMNS: Column<User>[] = [
  {
    key: 'email',
    header: 'Email',
    cell: (u) => <span className="font-mono text-xs">{u.email}</span>,
    sortValue: (u) => u.email,
  },
  { key: 'name', header: 'Name', cell: (u) => u.display_name, sortValue: (u) => u.display_name },
  {
    key: 'role',
    header: 'Role',
    cell: (u) => (
      <Pill tone={u.role === 'admin' ? 'primary' : 'neutral'}>{ROLE_LABELS[u.role]}</Pill>
    ),
    sortValue: (u) => ROLE_LABELS[u.role],
  },
  {
    key: 'demo',
    header: 'Demo account',
    cell: (u) =>
      u.is_demo ? (
        <Pill tone="demo" icon={<FlaskConical aria-hidden />}>
          Demo
        </Pill>
      ) : (
        <span className="text-muted-foreground">No</span>
      ),
    sortValue: (u) => (u.is_demo ? 1 : 0),
  },
  {
    key: 'last-login',
    header: 'Last login',
    cell: (u) => (
      <span className="whitespace-nowrap text-muted-foreground">
        {u.last_login_at ? fmtDateTime(u.last_login_at) : 'Never'}
      </span>
    ),
    sortValue: (u) => u.last_login_at,
  },
]

function shortJson(details: Record<string, unknown>): string {
  const text = JSON.stringify(details ?? {})
  return text.length > 90 ? `${text.slice(0, 87)}...` : text
}

const AUDIT_COLUMNS: Column<AuditEntry>[] = [
  {
    key: 'time',
    header: 'Time',
    cell: (a) => <span className="whitespace-nowrap">{fmtDateTime(a.created_at)}</span>,
    sortValue: (a) => a.created_at,
  },
  {
    key: 'action',
    header: 'Action',
    cell: (a) => <span className="font-mono text-xs">{a.action}</span>,
    sortValue: (a) => a.action,
  },
  {
    key: 'entity',
    header: 'Entity',
    cell: (a) =>
      a.entity_type ? (
        <span className="text-sm">
          {a.entity_type}
          {a.entity_id && (
            <span className="block max-w-[16rem] truncate font-mono text-xs text-muted-foreground">
              {a.entity_id}
            </span>
          )}
        </span>
      ) : (
        <span className="text-muted-foreground">-</span>
      ),
    sortValue: (a) => a.entity_type,
  },
  {
    key: 'details',
    header: 'Details',
    cell: (a) => {
      const full = JSON.stringify(a.details ?? {})
      return (
        <code
          className="block max-w-[28rem] truncate font-mono text-xs text-muted-foreground"
          title={full}
        >
          {shortJson(a.details)}
        </code>
      )
    },
  },
]

// ---------------------------------------------------------------- page
export default function AdminPage() {
  const { t } = useTranslation()
  const session = useSession()
  const demo = useDemoState()
  const isApi = session.mode === 'api'
  const isAdmin = session.user?.role === 'admin'
  const isApiAdmin = isApi && isAdmin

  const pipeline = useRunPipeline()
  const simulate = useSimulateEvExpansion()
  const reset = useResetDemo()
  const health = useHealth()
  const db = useDbHealth()
  const users = useUsers(isApiAdmin)
  const audit = useAuditLog(isApiAdmin)

  const [confirmReset, setConfirmReset] = useState(false)

  const lockedReason = !isApi
    ? 'You are in offline demo mode, so there is no API to call. Sign in to the local API with an admin account.'
    : `You are signed in as ${ROLE_LABELS[session.user?.role ?? 'candidate']}. Only platform admins can use this.`

  const counts = {
    decisions: Object.keys(demo.recommendationStatus).length,
    validations: Object.keys(demo.validations).length,
    pledges: demo.pledges.length,
    planActions: Object.keys(demo.planActionStatus).length,
    submissions: demo.demandSubmissions.length,
  }
  const storedTotal =
    counts.decisions +
    counts.validations +
    counts.pledges +
    counts.planActions +
    counts.submissions +
    (demo.planSubmitted ? 1 : 0)

  function runPipeline() {
    pipeline.mutate(undefined, {
      onSuccess: (result) =>
        toast.success(`Pipeline run finished for ${result.quarter}`, {
          description: `${fmtInt(result.mismatch_rows)} mismatch rows recomputed. Analytics pages now show the new run.`,
        }),
      onError: (error) => toast.error(`Pipeline run failed: ${errorMessage(error)}`),
    })
  }

  function toggleSimulation() {
    const next = !demo.evExpansionSimulated
    simulate.mutate(next, {
      onSuccess: () =>
        next
          ? toast.success('Nashik EV expansion simulated', {
              description:
                'A banner, a notification and a market signal now show the simulated event.',
            })
          : toast.info('Simulation turned off'),
      onError: (error) => toast.error(errorMessage(error)),
    })
  }

  function resetDemo() {
    reset.mutate(undefined, {
      onSuccess: () => {
        setConfirmReset(false)
        toast.success('Demo reset', {
          description:
            'Decisions, validations, pledges and plan progress in this browser were cleared.',
        })
      },
      onError: (error) => toast.error(errorMessage(error)),
    })
  }

  const apiState = health.isPending ? 'checking' : health.isError ? 'error' : 'ok'
  const dbState = db.isPending ? 'checking' : db.isError ? 'error' : 'ok'

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Administration"
        title={t('pages.admin')}
        description="Run the analytics pipeline, show the simulated Nashik EV event and reset demo actions. Everything here works on the synthetic demo world."
        badges={<SyntheticBadge />}
        actions={
          <Pill
            tone={isApi ? 'info' : 'demo'}
            icon={isApi ? <Database aria-hidden /> : <FlaskConical aria-hidden />}
          >
            {isApi ? 'Live API session' : 'Offline demo session'}
          </Pill>
        }
      />

      {/* ------------------------------------------------------------ controls */}
      <div className="grid gap-6 lg:grid-cols-2 2xl:grid-cols-3">
        {/* a. pipeline */}
        <ControlCard
          icon={<Cpu aria-hidden />}
          title="Run intelligence pipeline"
          status={
            pipeline.isPending ? (
              <Pill tone="info" icon={<LoaderCircle className="animate-spin" aria-hidden />}>
                Running
              </Pill>
            ) : isApiAdmin ? (
              <Pill tone="success" icon={<CircleCheck aria-hidden />}>
                Ready
              </Pill>
            ) : (
              <Pill icon={<Lock aria-hidden />}>Needs API + admin</Pill>
            )
          }
          description={
            <p>
              Recomputes demand, training supply and mismatch on the backend from the stored
              synthetic signals, and records a new pipeline run with its scoring config.
            </p>
          }
          footer={
            <>
              <Button onClick={runPipeline} disabled={!isApiAdmin || pipeline.isPending}>
                {pipeline.isPending ? (
                  <LoaderCircle className="animate-spin" aria-hidden />
                ) : (
                  <Play aria-hidden />
                )}
                {pipeline.isPending ? 'Running pipeline...' : 'Run pipeline'}
              </Button>
              {pipeline.isSuccess && <DataSourceBadge source="live" />}
            </>
          }
        >
          <div aria-live="polite" className="space-y-3">
            {!isApiAdmin && (
              <Callout
                tone="warning"
                icon={<Lock aria-hidden />}
                title="Needs the API and an admin account"
              >
                {lockedReason}
              </Callout>
            )}
            {pipeline.isPending && (
              <p className="flex items-center gap-2 rounded-lg bg-info-soft px-3 py-2 text-sm text-info">
                <LoaderCircle className="size-4 shrink-0 animate-spin" aria-hidden />
                Computing demand → supply → mismatch for {DISTRICTS.length} districts...
              </p>
            )}
            {pipeline.isError && (
              <p
                role="alert"
                className="rounded-lg border border-danger/25 bg-danger-soft px-3 py-2 text-sm text-danger"
              >
                Pipeline run failed: {errorMessage(pipeline.error)}
              </p>
            )}
            {pipeline.data && (
              <div className="rounded-lg border border-success/25 bg-success-soft/50 p-3">
                <p className="mb-2 flex items-center gap-1.5 text-sm font-medium text-success">
                  <CircleCheck className="size-4" aria-hidden /> Run finished
                </p>
                <dl className="grid grid-cols-2 gap-2">
                  <Stat
                    label="Pipeline run ID"
                    value={pipeline.data.pipeline_run_id}
                    mono
                    className="col-span-2"
                  />
                  <Stat label="Quarter" value={pipeline.data.quarter} />
                  <Stat label="Demand rows" value={fmtInt(pipeline.data.demand_rows)} />
                  <Stat label="Skill rows" value={fmtInt(pipeline.data.skill_rows)} />
                  <Stat label="Supply rows" value={fmtInt(pipeline.data.supply_rows)} />
                  <Stat label="Mismatch rows" value={fmtInt(pipeline.data.mismatch_rows)} />
                </dl>
              </div>
            )}
          </div>
        </ControlCard>

        {/* b. EV expansion */}
        <ControlCard
          icon={<Zap aria-hidden />}
          title="Simulate Nashik EV expansion"
          status={
            demo.evExpansionSimulated ? (
              <Pill tone="demo" icon={<FlaskConical aria-hidden />}>
                Simulation on
              </Pill>
            ) : (
              <Pill>Simulation off</Pill>
            )
          }
          description={
            <p>
              Surfaces the demo world&apos;s simulated EV battery-pack assembly unit in Nashik
              (about 180 EV Service Technician jobs expected 2026Q4–2027Q3, a{' '}
              <strong className="font-semibold text-foreground">SIMULATED</strong> synthetic event)
              as a banner, notification and market signal.
            </p>
          }
          footer={
            <>
              <Button
                variant={demo.evExpansionSimulated ? 'outline' : 'default'}
                onClick={toggleSimulation}
                disabled={simulate.isPending}
                aria-pressed={demo.evExpansionSimulated}
              >
                <Zap aria-hidden />
                {demo.evExpansionSimulated ? 'Turn off simulation' : 'Simulate'}
              </Button>
              <Button variant="link" asChild>
                <Link to="/districts/MH-NASHIK">Open Nashik</Link>
              </Button>
            </>
          }
        >
          <Callout tone="demo" icon={<FlaskConical aria-hidden />}>
            Not a real announcement. The switch is stored in this browser only.
          </Callout>
        </ControlCard>

        {/* c. reset */}
        <ControlCard
          icon={<RotateCcw aria-hidden />}
          title="Reset demo"
          status={
            storedTotal > 0 ? (
              <Pill tone="warning">{fmtInt(storedTotal)} stored actions</Pill>
            ) : (
              <Pill tone="success" icon={<CircleCheck aria-hidden />}>
                Clean state
              </Pill>
            )
          }
          description={
            <p>
              Clears recommendation decisions, employer validations, pledges and plan progress
              stored in this browser, so the walkthrough can start again. Backend data is not
              touched.
            </p>
          }
          footer={
            <Button
              variant="destructive"
              onClick={() => setConfirmReset(true)}
              disabled={reset.isPending}
            >
              <RotateCcw aria-hidden /> Reset demo...
            </Button>
          }
        >
          <dl
            className="grid grid-cols-2 gap-2 sm:grid-cols-3"
            aria-label="Demo actions stored in this browser"
          >
            <Stat label="Decisions" value={fmtInt(counts.decisions)} />
            <Stat label="Validations" value={fmtInt(counts.validations)} />
            <Stat label="Pledges" value={fmtInt(counts.pledges)} />
            <Stat label="Plan actions" value={fmtInt(counts.planActions)} />
            <Stat label="Demand forms" value={fmtInt(counts.submissions)} />
            <Stat label="Plan submitted" value={demo.planSubmitted ? 'Yes' : 'No'} />
          </dl>
        </ControlCard>
      </div>

      <ConfirmDialog
        open={confirmReset}
        onOpenChange={setConfirmReset}
        destructive
        pending={reset.isPending}
        title="Reset the demo?"
        description={`This clears ${counts.decisions} recommendation decisions, ${counts.validations} employer validations, ${counts.pledges} pledges and all plan progress stored in this browser${demo.evExpansionSimulated ? ', and turns off the EV expansion simulation' : ''}. It cannot be undone.`}
        confirmLabel="Reset demo"
        onConfirm={resetDemo}
      />

      {/* ------------------------------------------------------------ status + mode */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Panel
          title="System status"
          description="Health of the backend API and its database."
          actions={
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  void health.refetch()
                  void db.refetch()
                }}
                disabled={health.isFetching || db.isFetching}
              >
                <RefreshCw className={cn(health.isFetching && 'animate-spin')} aria-hidden /> Check
                again
              </Button>
              <Button variant="ghost" size="sm" asChild>
                <Link to="/status">
                  <Activity aria-hidden /> Status page
                </Link>
              </Button>
            </>
          }
        >
          <dl className="divide-y" aria-live="polite">
            <InfoRow
              label="Backend API"
              hint={
                health.isError
                  ? `${errorMessage(health.error)} Pages fall back to labelled demo data.`
                  : health.data
                    ? `${health.data.service} · status ${health.data.status}`
                    : undefined
              }
            >
              <Check state={apiState}>
                {apiState === 'checking'
                  ? 'Checking...'
                  : apiState === 'ok'
                    ? 'Online'
                    : 'API offline'}
              </Check>
            </InfoRow>
            <InfoRow label="Environment">
              <span className="font-mono text-xs">{health.data?.env ?? '-'}</span>
            </InfoRow>
            <InfoRow label="API version">
              <span className="font-mono text-xs">{health.data?.version ?? '-'}</span>
            </InfoRow>
            <InfoRow
              label="Scoring config"
              hint={
                health.data?.scoring_config_sha256
                  ? `SHA-256 ${health.data.scoring_config_sha256.slice(0, 12)}…`
                  : 'config/scoring.yaml'
              }
            >
              <span className="font-mono text-xs">
                {health.data?.scoring_config_version ?? '-'}
              </span>
            </InfoRow>
            <InfoRow
              label="Database"
              hint={db.isError ? errorMessage(db.error) : db.data?.database}
            >
              <Check state={dbState}>
                {dbState === 'checking'
                  ? 'Checking...'
                  : dbState === 'ok'
                    ? 'Connected'
                    : 'Not reachable'}
              </Check>
            </InfoRow>
            <InfoRow label="pgvector">
              {db.data ? (
                <Check state={db.data.pgvector.installed ? 'ok' : 'error'}>
                  {db.data.pgvector.installed
                    ? `Version ${db.data.pgvector.version ?? '?'}`
                    : 'Not installed'}
                </Check>
              ) : (
                <span className="text-muted-foreground">
                  {db.isPending ? 'Checking...' : 'Unknown'}
                </span>
              )}
            </InfoRow>
          </dl>
        </Panel>

        <Panel title="Data mode" description="Where the numbers on each page come from.">
          <dl className="divide-y">
            <InfoRow
              label="Session"
              hint={
                isApi
                  ? 'Pages read the KaushalSetu API. Its database holds the synthetic demo world.'
                  : 'No API session: every page shows the built-in demo data.'
              }
            >
              <Pill
                tone={isApi ? 'info' : 'demo'}
                icon={isApi ? <Database aria-hidden /> : <FlaskConical aria-hidden />}
              >
                {isApi ? 'Live API' : 'Offline demo'}
              </Pill>
            </InfoRow>
            <InfoRow label="Signed in as" hint={session.user?.email}>
              <span className="font-medium">{session.user?.display_name ?? '-'}</span>
              {session.user && <Pill>{ROLE_LABELS[session.user.role]}</Pill>}
            </InfoRow>
            <InfoRow
              label="Demo fallback"
              hint={
                DEMO_FALLBACK_ENABLED
                  ? 'When an API call fails or an endpoint is not built yet, pages show deterministic demo data labelled "Demo data".'
                  : 'Fallback is off: pages show the API error instead of demo data.'
              }
            >
              <Pill
                tone={DEMO_FALLBACK_ENABLED ? 'success' : 'neutral'}
                icon={DEMO_FALLBACK_ENABLED ? <CircleCheck aria-hidden /> : <CircleX aria-hidden />}
              >
                {DEMO_FALLBACK_ENABLED ? 'Enabled' : 'Disabled'}
              </Pill>
            </InfoRow>
          </dl>
          <div className="mt-4 space-y-3">
            <p className="text-sm text-muted-foreground">
              Set{' '}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs text-foreground">
                VITE_DEMO_FALLBACK=false
              </code>{' '}
              in{' '}
              <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs text-foreground">
                frontend/.env.local
              </code>{' '}
              and restart the dev server to turn the fallback off.
            </p>
            <div className="flex flex-wrap items-center gap-2 rounded-lg bg-muted/60 px-3 py-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">Labels used on every page:</span>
              <DataSourceBadge source="live" />
              <DataSourceBadge source="demo" />
            </div>
          </div>
        </Panel>
      </div>

      {/* ------------------------------------------------------------ live admin data */}
      <Panel
        title={
          <span className="inline-flex items-center gap-2">
            <Users className="size-4 text-primary" aria-hidden /> Users
          </span>
        }
        description="Accounts in the local API database."
        actions={isApiAdmin && users.isSuccess ? <DataSourceBadge source="live" /> : undefined}
      >
        {isApiAdmin ? (
          <QueryState
            query={users}
            empty={
              <EmptyState
                title="No users"
                description="Create demo accounts with python -m app.cli.demo_users."
              />
            }
          >
            {(rows) => (
              <DataTable
                rows={rows}
                columns={USER_COLUMNS}
                rowKey={(u) => u.id}
                caption="Users"
                initialSort={{ key: 'role', desc: false }}
                dense
              />
            )}
          </QueryState>
        ) : (
          <EmptyState
            icon={<Lock aria-hidden />}
            title="Needs the API and an admin account"
            description={lockedReason}
          />
        )}
      </Panel>

      <Panel
        title={
          <span className="inline-flex items-center gap-2">
            <ScrollText className="size-4 text-primary" aria-hidden /> Recent audit log
          </span>
        }
        description="The latest recorded actions (sign-ins, pipeline runs and other changes)."
        actions={isApiAdmin && audit.isSuccess ? <DataSourceBadge source="live" /> : undefined}
      >
        {isApiAdmin ? (
          <QueryState
            query={audit}
            empty={
              <EmptyState
                title="No audit entries yet"
                description="Actions such as sign-ins and pipeline runs appear here."
              />
            }
          >
            {(rows) => (
              <DataTable
                rows={rows}
                columns={AUDIT_COLUMNS}
                rowKey={(a) => a.id}
                caption="Recent audit log"
                initialSort={{ key: 'time', desc: true }}
                dense
              />
            )}
          </QueryState>
        ) : (
          <EmptyState
            icon={<Lock aria-hidden />}
            title="Needs the API and an admin account"
            description={lockedReason}
          />
        )}
      </Panel>
    </div>
  )
}
