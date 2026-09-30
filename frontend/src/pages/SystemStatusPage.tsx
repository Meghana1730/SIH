import { useCallback, useEffect, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { ApiError, apiFetch } from '@/lib/api/client'
import type { ApiHealth, DbHealth } from '@/lib/api/types'

// Each check is either still running, passed, or failed. The text is always shown,
// so the status never depends on colour alone.
type CheckState =
  | { kind: 'checking' }
  | { kind: 'ok'; detail: string }
  | { kind: 'error'; detail: string }
  | { kind: 'absent'; detail: string }

type Checks = { api: CheckState; database: CheckState; pgvector: CheckState }

const CHECKING: Checks = {
  api: { kind: 'checking' },
  database: { kind: 'checking' },
  pgvector: { kind: 'checking' },
}

async function runChecks(signal: AbortSignal): Promise<Checks> {
  const [api, db] = await Promise.allSettled([
    apiFetch<ApiHealth>('/health', { signal, auth: false }),
    apiFetch<DbHealth>('/health/db', { signal, auth: false }),
  ])

  // A frontend-only deployment (static host, no backend) answers /health with the web page.
  if (
    api.status === 'rejected' &&
    api.reason instanceof ApiError &&
    api.reason.code === 'NOT_JSON'
  ) {
    const absent: CheckState = {
      kind: 'absent',
      detail: 'No backend is connected to this website: it runs on built-in demo data.',
    }
    return { api: absent, database: absent, pgvector: absent }
  }

  const apiState: CheckState =
    api.status === 'fulfilled'
      ? {
          kind: 'ok',
          detail:
            `${api.value.service} v${api.value.version} (${api.value.env}) · ` +
            `scoring config ${api.value.scoring_config_version}`,
        }
      : {
          kind: 'error',
          detail:
            'Backend not reachable (locally: is uvicorn running on port 8000? Online: a free server may be waking up; try again in a minute).',
        }

  if (db.status === 'rejected') {
    return {
      api: apiState,
      database: {
        kind: 'error',
        detail: 'Database not reachable (locally: is the db container running?).',
      },
      pgvector: { kind: 'error', detail: 'Unknown (database not reachable)' },
    }
  }

  const { pgvector } = db.value
  return {
    api: apiState,
    database: { kind: 'ok', detail: db.value.database },
    pgvector: pgvector.installed
      ? { kind: 'ok', detail: `version ${pgvector.version}` }
      : { kind: 'error', detail: 'Not enabled. Run: alembic upgrade head' },
  }
}

function StatusRow({ label, state, testId }: { label: string; state: CheckState; testId: string }) {
  return (
    <li className="flex items-start justify-between gap-4 py-3" data-testid={testId}>
      <div>
        <p className="font-medium">{label}</p>
        {state.kind !== 'checking' && (
          <p className="text-sm text-muted-foreground">{state.detail}</p>
        )}
      </div>
      {state.kind === 'checking' && <Badge variant="outline">Checking…</Badge>}
      {state.kind === 'ok' && <Badge>OK</Badge>}
      {state.kind === 'error' && <Badge variant="destructive">Problem</Badge>}
      {state.kind === 'absent' && <Badge variant="outline">Not connected</Badge>}
    </li>
  )
}

export default function SystemStatusPage() {
  const [checks, setChecks] = useState<Checks>(CHECKING)
  const [runId, setRunId] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    runChecks(controller.signal)
      .then(setChecks)
      .catch(() => {
        /* aborted because the page re-rendered or closed; nothing to do */
      })
    return () => controller.abort()
  }, [runId])

  const checkAgain = useCallback(() => {
    setChecks(CHECKING)
    setRunId((n) => n + 1)
  }, [])

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-6 px-4 py-10">
      <header className="space-y-1">
        <h1 className="text-3xl font-semibold tracking-tight">InnovProcure</h1>
        <p className="text-muted-foreground">
          Labour-market intelligence and curriculum alignment · prototype on synthetic demo data
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>System status</CardTitle>
          <CardDescription>
            Checks that the frontend, backend API and database are connected.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="divide-y">
            <StatusRow label="Backend API" state={checks.api} testId="status-api" />
            <StatusRow label="PostgreSQL database" state={checks.database} testId="status-db" />
            <StatusRow
              label="pgvector extension"
              state={checks.pgvector}
              testId="status-pgvector"
            />
          </ul>
        </CardContent>
        <CardFooter>
          <Button variant="outline" onClick={checkAgain}>
            Check again
          </Button>
        </CardFooter>
      </Card>
    </main>
  )
}
