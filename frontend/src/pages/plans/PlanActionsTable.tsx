// Actions of a district plan, with a status picker per action (useSetPlanAction).
import { ArrowUpRight, Circle, CircleCheck, Clock } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'

import { StatusBadge } from '@/components/badges'
import { DataTable, type Column } from '@/components/DataTable'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { errorMessage, useRecommendations, useSetPlanAction } from '@/lib/api/queries'
import type { PlanAction } from '@/lib/api/types'
import { fmtDate } from '@/lib/format'

type ActionStatus = PlanAction['status']

const STATUS_OPTIONS: { value: ActionStatus; label: string; icon: ReactNode }[] = [
  {
    value: 'PLANNED',
    label: 'Planned',
    icon: <Circle className="text-muted-foreground" aria-hidden />,
  },
  { value: 'IN_PROGRESS', label: 'In progress', icon: <Clock className="text-info" aria-hidden /> },
  { value: 'DONE', label: 'Done', icon: <CircleCheck className="text-success" aria-hidden /> },
]

function statusLabel(status: ActionStatus): string {
  return STATUS_OPTIONS.find((o) => o.value === status)?.label ?? status
}

export function PlanActionsTable({ actions }: { actions: PlanAction[] }) {
  const setAction = useSetPlanAction()
  const recommendations = useRecommendations()
  const recTitle = (id: string) =>
    recommendations.data?.data.find((r) => r.id === id)?.title ?? 'View recommendation'

  const done = actions.filter((a) => a.status === 'DONE').length
  const inProgress = actions.filter((a) => a.status === 'IN_PROGRESS').length
  const pct = actions.length ? Math.round((done / actions.length) * 100) : 0

  function change(action: PlanAction, status: ActionStatus) {
    if (status === action.status) return
    setAction.mutate(
      { id: action.id, status },
      {
        onSuccess: () =>
          toast.success(`Action marked ${statusLabel(status).toLowerCase()}`, {
            description: action.title,
          }),
        onError: (error) => toast.error(errorMessage(error)),
      },
    )
  }

  const columns: Column<PlanAction>[] = [
    {
      key: 'title',
      header: 'Action',
      className: 'min-w-64 whitespace-normal',
      cell: (a) => <span className="font-medium">{a.title}</span>,
    },
    {
      key: 'owner',
      header: 'Owner',
      className: 'min-w-40 whitespace-normal',
      cell: (a) => <span className="text-muted-foreground">{a.owner}</span>,
    },
    {
      key: 'due',
      header: 'Due',
      sortValue: (a) => a.due,
      className: 'whitespace-nowrap',
      cell: (a) => <span className="tabular">{fmtDate(a.due)}</span>,
    },
    {
      key: 'status',
      header: 'Status',
      sortValue: (a) => STATUS_OPTIONS.findIndex((o) => o.value === a.status),
      cell: (a) => {
        const saving = setAction.isPending && setAction.variables?.id === a.id
        return (
          <>
            <span className="hidden print:inline">
              <StatusBadge status={a.status} />
            </span>
            <Select
              value={a.status}
              onValueChange={(value) => change(a, value as ActionStatus)}
              disabled={saving}
            >
              <SelectTrigger
                size="sm"
                aria-label={`Status of action: ${a.title}`}
                className="w-36 bg-card print:hidden"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.icon}
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </>
        )
      },
    },
    {
      key: 'rec',
      header: 'Linked recommendation',
      className: 'min-w-48 whitespace-normal',
      cell: (a) =>
        a.linked_recommendation ? (
          <Link
            to={`/recommendations/${a.linked_recommendation}`}
            className="inline-flex items-start gap-1 rounded text-sm font-medium text-primary hover:underline focus-visible:outline-2"
          >
            {recTitle(a.linked_recommendation)}
            <ArrowUpRight className="mt-0.5 size-3.5 shrink-0 print:hidden" aria-hidden />
          </Link>
        ) : (
          <span className="text-muted-foreground">-</span>
        ),
    },
  ]

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
        <p>
          <span className="tabular font-semibold">{done}</span> of{' '}
          <span className="tabular font-semibold">{actions.length}</span> actions done
          <span className="text-muted-foreground">
            {' '}
            · <span className="tabular">{inProgress}</span> in progress
          </span>
        </p>
        <div
          className="h-2 min-w-40 flex-1 overflow-hidden rounded-full bg-muted"
          role="progressbar"
          aria-label="Plan actions done"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          aria-valuetext={`${done} of ${actions.length} actions done`}
        >
          <div className="h-full rounded-full bg-success" style={{ width: `${pct}%` }} />
        </div>
      </div>
      <DataTable
        rows={actions}
        columns={columns}
        rowKey={(a) => a.id}
        caption="Plan actions with owner, due date, status and linked recommendation"
      />
    </div>
  )
}
