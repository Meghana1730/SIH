// District Plans (/district-plans): the list of district plans and the selected plan as a
// printable document. Only Nashik has a plan in the demo; it reflects the employer demo actions
// (pledges, validations) kept in this browser.
import { FileText } from 'lucide-react'
import { useState } from 'react'

import { StatusBadge } from '@/components/badges'
import { PageHeader, Panel } from '@/components/headers'
import { EmptyState, QueryState } from '@/components/states'
import { Skeleton } from '@/components/ui/skeleton'
import { usePlans } from '@/lib/api/queries'
import type { DistrictPlan } from '@/lib/api/types'
import { DISTRICTS } from '@/lib/demo/catalog'
import { cn } from '@/lib/utils'
import { PlanDocument } from '@/pages/plans/PlanDocument'
import { PLAN_PRINT_CSS } from '@/pages/plans/printStyles'

function PlanList({
  plans,
  pending,
  failed,
  selected,
  onSelect,
}: {
  plans: DistrictPlan[]
  pending: boolean
  failed: boolean
  selected: string | undefined
  onSelect: (district: string) => void
}) {
  return (
    <nav aria-label="District plans" data-print-hide className="lg:sticky lg:top-20">
      <Panel title="Districts" description="One skill plan per district" bodyClassName="p-2">
        <ul className="space-y-1">
          {DISTRICTS.map((district) => {
            const plan = plans.find((p) => p.district.code === district.code)
            if (!plan) {
              return (
                <li
                  key={district.code}
                  className="flex items-center justify-between gap-2 rounded-lg px-3 py-2.5 text-sm text-muted-foreground"
                >
                  <span>{district.name}</span>
                  {pending ? (
                    <Skeleton className="h-5 w-20" />
                  ) : (
                    <span className="rounded-md border border-dashed px-2 py-0.5 text-xs">
                      {failed ? 'Unavailable' : 'No plan yet'}
                    </span>
                  )}
                </li>
              )
            }
            const active = plan.district.code === selected
            return (
              <li key={district.code}>
                <button
                  type="button"
                  aria-pressed={active}
                  onClick={() => onSelect(plan.district.code)}
                  className={cn(
                    'flex w-full items-start justify-between gap-2 rounded-lg px-3 py-2.5 text-left transition-colors focus-visible:outline-2',
                    active ? 'bg-accent shadow-[inset_3px_0_0_var(--primary)]' : 'hover:bg-muted',
                  )}
                >
                  <span className="min-w-0">
                    <span className="flex items-center gap-1.5 text-sm font-medium">
                      <FileText className="size-3.5 text-primary" aria-hidden />
                      {district.name}
                    </span>
                    <span className="mt-0.5 block text-xs text-muted-foreground">
                      {plan.period}
                    </span>
                  </span>
                  <StatusBadge status={plan.status} />
                </button>
              </li>
            )
          })}
        </ul>
      </Panel>
    </nav>
  )
}

export default function DistrictPlansPage() {
  const plans = usePlans()
  const [selected, setSelected] = useState('MH-NASHIK')
  const list = plans.data?.data ?? []
  const current = list.find((p) => p.district.code === selected) ?? list[0]

  return (
    <>
      <style>{PLAN_PRINT_CSS}</style>
      <PageHeader
        eyebrow="Planning"
        title="District Plans"
        description="District skill plans drafted from the demand, supply and recommendation analysis. Employer pledges and validations made in the Employer portal flow into the plan."
      />

      <div
        data-print-layout
        className="grid items-start gap-6 lg:grid-cols-[260px_minmax(0,1fr)] 2xl:grid-cols-[300px_minmax(0,1fr)]"
      >
        <PlanList
          plans={list}
          pending={plans.isPending}
          failed={plans.isError}
          selected={current?.district.code}
          onSelect={setSelected}
        />

        <div className="min-w-0">
          <QueryState
            query={plans}
            loadingRows={6}
            isEmpty={(res) => res.data.length === 0}
            empty={
              <EmptyState
                title="No district plans yet"
                description="Plans appear here once a district drafts one."
              />
            }
          >
            {(res) =>
              current ? <PlanDocument plan={current} source={res.source} note={res.note} /> : null
            }
          </QueryState>
        </div>
      </div>
    </>
  )
}
