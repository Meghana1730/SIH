import {
  BadgeCheck,
  Building2,
  CheckCircle2,
  ClipboardList,
  Handshake,
  History,
} from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'

import { DataSourceBadge, Pill, PriorityBadge, SyntheticBadge } from '@/components/badges'
import { ActionBadge, Callout } from '@/components/cards'
import { PageHeader, Panel } from '@/components/headers'
import { EmptyState, QueryState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import {
  useCourses,
  useEmployerActivity,
  useEmployers,
  usePledge,
  useRecommendations,
  useSubmitDemand,
  useValidateRecommendation,
} from '@/lib/api/queries'
import type { Employer, Recommendation } from '@/lib/api/types'
import { ROLES, SKILL_NAMES, skillSector } from '@/lib/demo/catalog'
import { DEMO_EMPLOYER_CODE } from '@/lib/demo/people'
import { KEY_RECOMMENDATION_ID } from '@/lib/demo/recommendations'
import { useDemoState } from '@/lib/demo/store'
import { fmtDateTime, sectorLabel } from '@/lib/format'

const QUARTERS = ['2026Q4', '2027Q1', '2027Q2', '2027Q3']

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null
  return (
    <p id={id} role="alert" className="text-xs font-medium text-danger">
      {message}
    </p>
  )
}

// ---------------------------------------------------------------- validation
function ValidateRecommendation({ rec }: { rec: Recommendation }) {
  const demo = useDemoState()
  const validate = useValidateRecommendation()
  const existing = demo.validations[rec.id]
  const [agree, setAgree] = useState<'yes' | 'no' | ''>('')
  const [comment, setComment] = useState('')
  const [error, setError] = useState<string>()

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!agree) {
      setError('Choose whether you agree with this recommendation.')
      return
    }
    if (comment.length > 500) {
      setError('Keep the comment under 500 characters.')
      return
    }
    setError(undefined)
    validate.mutate(
      { recommendationId: rec.id, agree: agree === 'yes', comment: comment.trim() },
      {
        onSuccess: () =>
          toast.success(agree === 'yes' ? 'Recommendation endorsed' : 'Feedback recorded', {
            description: 'Saved as demo data in this browser.',
          }),
      },
    )
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-muted/40 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <ActionBadge action={rec.action} />
          <PriorityBadge priority={rec.priority} score={rec.priority_score} />
        </div>
        <p className="mt-2 font-semibold">{rec.title}</p>
        <p className="text-sm text-muted-foreground">{rec.target}</p>
        <p className="mt-2 text-sm text-muted-foreground">{rec.reason}</p>
        <ul className="mt-3 space-y-1 text-sm">
          {rec.evidence.slice(0, 3).map((e) => (
            <li key={e.label} className="flex gap-2">
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
              <span className="text-muted-foreground">{e.detail}</span>
            </li>
          ))}
        </ul>
      </div>

      {existing ? (
        <Callout
          tone="success"
          title="Thank you: your validation is recorded"
          icon={<BadgeCheck aria-hidden />}
        >
          You {existing.agree ? 'endorsed' : 'disagreed with'} this recommendation on{' '}
          {fmtDateTime(existing.at)}.{existing.comment ? ` Comment: "${existing.comment}"` : ''} It
          now counts towards the recommendation's employer validations (demo data, this browser
          only).
        </Callout>
      ) : (
        <form onSubmit={submit} className="space-y-4" noValidate>
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">
              Would graduates with this module be easier for you to hire?
            </legend>
            <RadioGroup
              value={agree}
              onValueChange={(value) => setAgree(value as 'yes' | 'no')}
              aria-describedby={error ? 'validate-error' : undefined}
              className="flex flex-wrap gap-4"
            >
              <Label className="flex items-center gap-2 rounded-lg border px-3 py-2 font-normal">
                <RadioGroupItem value="yes" /> Yes, I agree
              </Label>
              <Label className="flex items-center gap-2 rounded-lg border px-3 py-2 font-normal">
                <RadioGroupItem value="no" /> No, it would not help
              </Label>
            </RadioGroup>
          </fieldset>
          <div className="space-y-1.5">
            <Label htmlFor="validate-comment">Comment (optional)</Label>
            <Textarea
              id="validate-comment"
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              placeholder="e.g. We need technicians who can read BMS fault codes."
              maxLength={600}
              rows={3}
            />
            <p className="text-xs text-muted-foreground">{comment.length}/500</p>
          </div>
          <FieldError id="validate-error" message={error} />
          <Button type="submit" disabled={validate.isPending}>
            <BadgeCheck aria-hidden /> {validate.isPending ? 'Saving...' : 'Submit validation'}
          </Button>
        </form>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- pledge
function PledgeForm({ employer }: { employer: Employer }) {
  const navigate = useNavigate()
  const courses = useCourses()
  const pledge = usePledge()
  const demo = useDemoState()
  const local = (courses.data?.data ?? []).filter((c) => c.district.code === employer.district.code)
  const [courseId, setCourseId] = useState('nsk-iti-a-electrician')
  const [seats, setSeats] = useState('35')
  const [quarter, setQuarter] = useState(QUARTERS[0])
  const [confirm, setConfirm] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const course = local.find((c) => c.id === courseId) ?? local[0]
  const pledged = demo.pledges.reduce((sum, p) => sum + p.seats, 0)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const found: Record<string, string> = {}
    const n = Number(seats)
    if (!course) found.course = 'Choose a course.'
    if (!Number.isInteger(n) || n < 1 || n > 200)
      found.seats = 'Enter a whole number of seats between 1 and 200.'
    if (!confirm) found.confirm = 'Please confirm the pledge.'
    setErrors(found)
    if (Object.keys(found).length || !course) return
    pledge.mutate(
      { employer_code: employer.code, course_id: course.id, seats: n, start_quarter: quarter },
      {
        onSuccess: () => {
          setConfirm(false)
          toast.success(`${n} apprenticeship seats pledged`, {
            description: `Added to the ${employer.district.name} district plan (demo data).`,
            action: { label: 'Open plan', onClick: () => navigate('/district-plans') },
          })
        },
      },
    )
  }

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5 sm:col-span-2">
          <Label id="pledge-course-label">Linked course</Label>
          <Select value={course?.id ?? ''} onValueChange={setCourseId}>
            <SelectTrigger
              aria-labelledby="pledge-course-label"
              className="w-full"
              aria-invalid={Boolean(errors.course)}
            >
              <SelectValue placeholder="Choose a course" />
            </SelectTrigger>
            <SelectContent>
              {local.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.name}, {c.institute.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <FieldError id="pledge-course-error" message={errors.course} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="pledge-seats">Apprenticeship seats</Label>
          <Input
            id="pledge-seats"
            type="number"
            inputMode="numeric"
            min={1}
            max={200}
            value={seats}
            onChange={(event) => setSeats(event.target.value)}
            aria-invalid={Boolean(errors.seats)}
            aria-describedby={errors.seats ? 'pledge-seats-error' : undefined}
          />
          <FieldError id="pledge-seats-error" message={errors.seats} />
        </div>
        <div className="space-y-1.5">
          <Label id="pledge-quarter-label">Start quarter</Label>
          <Select value={quarter} onValueChange={setQuarter}>
            <SelectTrigger aria-labelledby="pledge-quarter-label" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {QUARTERS.map((q) => (
                <SelectItem key={q} value={q}>
                  {q}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="flex items-start gap-2">
        <Checkbox
          id="pledge-confirm"
          checked={confirm}
          onCheckedChange={(value) => setConfirm(value === true)}
          aria-invalid={Boolean(errors.confirm)}
          aria-describedby={errors.confirm ? 'pledge-confirm-error' : undefined}
        />
        <Label htmlFor="pledge-confirm" className="text-sm leading-snug font-normal">
          I confirm {employer.name} intends to host these apprentices (demo pledge, not a legal
          commitment).
        </Label>
      </div>
      <FieldError id="pledge-confirm-error" message={errors.confirm} />
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={pledge.isPending}>
          <Handshake aria-hidden /> {pledge.isPending ? 'Saving...' : 'Pledge seats'}
        </Button>
        {pledged > 0 && (
          <p className="text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">{pledged}</span> seats pledged so far ·{' '}
            <Link to="/district-plans" className="font-medium text-primary hover:underline">
              see the district plan
            </Link>
          </p>
        )}
      </div>
    </form>
  )
}

// ---------------------------------------------------------------- hiring needs
function DemandForm({ employer }: { employer: Employer }) {
  const submitDemand = useSubmitDemand()
  const [role, setRole] = useState(
    ROLES.find((r) => r.sector === employer.sector)?.code ?? ROLES[0].code,
  )
  const [headcount, setHeadcount] = useState('10')
  const [horizon, setHorizon] = useState('6')
  const [skills, setSkills] = useState<string[]>([])
  const [notes, setNotes] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const roleSector = ROLES.find((r) => r.code === role)?.sector
  const skillOptions = Object.keys(SKILL_NAMES).filter(
    (code) =>
      skillSector(code) === roleSector ||
      ['electrical-safety', 'customer-communication'].includes(code),
  )

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const found: Record<string, string> = {}
    const n = Number(headcount)
    if (!Number.isInteger(n) || n < 1 || n > 500)
      found.headcount = 'Enter a whole number between 1 and 500.'
    if (skills.length === 0) found.skills = 'Pick at least one skill you need.'
    if (notes.length > 500) found.notes = 'Keep notes under 500 characters.'
    setErrors(found)
    if (Object.keys(found).length) return
    submitDemand.mutate(
      {
        employer_code: employer.code,
        role_code: role,
        skills,
        headcount: n,
        horizon_months: Number(horizon),
        notes,
      },
      {
        onSuccess: () => {
          toast.success('Hiring needs submitted', {
            description: 'Saved as demo data in this browser.',
          })
          setSkills([])
          setNotes('')
        },
      },
    )
  }

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1.5 sm:col-span-3">
          <Label id="demand-role-label">Role</Label>
          <Select
            value={role}
            onValueChange={(value) => {
              setRole(value)
              setSkills([])
            }}
          >
            <SelectTrigger aria-labelledby="demand-role-label" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ROLES.map((r) => (
                <SelectItem key={r.code} value={r.code}>
                  {r.title} · {sectorLabel(r.sector)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="demand-headcount">People needed</Label>
          <Input
            id="demand-headcount"
            type="number"
            min={1}
            max={500}
            value={headcount}
            onChange={(event) => setHeadcount(event.target.value)}
            aria-invalid={Boolean(errors.headcount)}
            aria-describedby={errors.headcount ? 'demand-headcount-error' : undefined}
          />
          <FieldError id="demand-headcount-error" message={errors.headcount} />
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label id="demand-horizon-label">Within</Label>
          <Select value={horizon} onValueChange={setHorizon}>
            <SelectTrigger aria-labelledby="demand-horizon-label" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="3">3 months</SelectItem>
              <SelectItem value="6">6 months</SelectItem>
              <SelectItem value="12">12 months</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <fieldset aria-describedby={errors.skills ? 'demand-skills-error' : undefined}>
        <legend className="mb-2 text-sm font-medium">Skills you need</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {skillOptions.map((code) => (
            <Label
              key={code}
              className="flex items-center gap-2 rounded-md border px-3 py-2 font-normal"
            >
              <Checkbox
                checked={skills.includes(code)}
                onCheckedChange={(checked) =>
                  setSkills((current) =>
                    checked === true ? [...current, code] : current.filter((c) => c !== code),
                  )
                }
              />
              {SKILL_NAMES[code]}
            </Label>
          ))}
        </div>
      </fieldset>
      <FieldError id="demand-skills-error" message={errors.skills} />
      <div className="space-y-1.5">
        <Label htmlFor="demand-notes">Notes (optional)</Label>
        <Textarea
          id="demand-notes"
          rows={2}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
        />
        <FieldError id="demand-notes-error" message={errors.notes} />
      </div>
      <Button type="submit" variant="outline" disabled={submitDemand.isPending}>
        <ClipboardList aria-hidden /> Submit hiring needs
      </Button>
    </form>
  )
}

// ---------------------------------------------------------------- page
export default function EmployerPage() {
  const location = useLocation()
  const employers = useEmployers()
  const recommendations = useRecommendations()
  const activity = useEmployerActivity()
  const [employerCode, setEmployerCode] = useState(DEMO_EMPLOYER_CODE)
  const employer =
    employers.data?.data.find((e) => e.code === employerCode) ?? employers.data?.data[0]
  const requested = (location.state as { recommendationId?: string } | null)?.recommendationId
  const toValidate = useMemo(() => {
    const all = recommendations.data?.data ?? []
    const first = all.find((r) => r.id === (requested ?? KEY_RECOMMENDATION_ID))
    const others = all.filter(
      (r) =>
        r.id !== first?.id &&
        r.district.code === employer?.district.code &&
        r.status !== 'DISMISSED',
    )
    return first && first.district.code === employer?.district.code ? [first, ...others] : others
  }, [recommendations.data, requested, employer])
  const [active, setActive] = useState<string | null>(null)
  const current = toValidate.find((r) => r.id === active) ?? toValidate[0]

  return (
    <div className="space-y-6">
      <PageHeader
        title="Employer Portal"
        description="Validate training recommendations, pledge apprenticeships and tell institutes what you are hiring for."
        badges={<DataSourceBadge source={employers.data?.source} note={employers.data?.note} />}
      />

      <QueryState query={employers} isEmpty={(d) => d.data.length === 0}>
        {() =>
          employer && (
            <section
              aria-label="Employer profile"
              className="flex flex-wrap items-center gap-4 rounded-xl border bg-card p-5 shadow-xs"
            >
              <span className="grid size-12 place-items-center rounded-xl bg-accent text-primary">
                <Building2 className="size-6" aria-hidden />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-lg font-semibold">{employer.name}</p>
                  <SyntheticBadge />
                </div>
                <p className="text-sm text-muted-foreground">
                  {employer.district.name} · {sectorLabel(employer.sector)} ·{' '}
                  {employer.size.toLowerCase()} enterprise
                </p>
              </div>
              <div className="space-y-1">
                <Label id="employer-switch" className="text-xs text-muted-foreground">
                  Viewing as (demo)
                </Label>
                <Select value={employer.code} onValueChange={setEmployerCode}>
                  <SelectTrigger aria-labelledby="employer-switch" className="w-72">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(employers.data?.data ?? []).map((e) => (
                      <SelectItem key={e.code} value={e.code}>
                        {e.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </section>
          )
        }
      </QueryState>

      {employer && (
        <div className="grid gap-6 xl:grid-cols-12">
          <Panel
            className="xl:col-span-7"
            title="Validate a recommendation"
            description={`Recommendations for ${employer.district.name} that need an employer's view.`}
            actions={
              <DataSourceBadge
                source={recommendations.data?.source}
                note={recommendations.data?.note}
              />
            }
          >
            {toValidate.length === 0 || !current ? (
              <EmptyState
                title="Nothing to validate"
                description="There are no open recommendations for your district."
              />
            ) : (
              <div className="space-y-4">
                {toValidate.length > 1 && (
                  <div
                    className="flex flex-wrap gap-2"
                    role="tablist"
                    aria-label="Recommendations to validate"
                  >
                    {toValidate.slice(0, 4).map((r) => (
                      <Button
                        key={r.id}
                        role="tab"
                        aria-selected={r.id === current.id}
                        size="sm"
                        variant={r.id === current.id ? 'secondary' : 'ghost'}
                        onClick={() => setActive(r.id)}
                      >
                        {r.title}
                      </Button>
                    ))}
                  </div>
                )}
                <ValidateRecommendation key={current.id} rec={current} />
              </div>
            )}
          </Panel>

          <div className="space-y-6 xl:col-span-5">
            <Panel
              title="Pledge apprenticeship seats"
              description="Host apprentices from a local course; pledges feed the district plan."
              actions={<Pill tone="demo">Demo action</Pill>}
            >
              <PledgeForm employer={employer} />
            </Panel>
            <Panel
              title="Recent activity"
              actions={<History className="size-4 text-muted-foreground" aria-hidden />}
            >
              <QueryState
                query={activity}
                isEmpty={(d) => d.data.length === 0}
                empty={
                  <p className="text-sm text-muted-foreground">
                    No submissions yet in this browser.
                  </p>
                }
              >
                {(result) => (
                  <ul className="space-y-3">
                    {result.data.slice(0, 6).map((a) => (
                      <li key={a.id} className="flex gap-3 text-sm">
                        <Pill
                          tone={
                            a.kind === 'PLEDGE'
                              ? 'success'
                              : a.kind === 'VALIDATION'
                                ? 'info'
                                : 'neutral'
                          }
                          className="h-5 text-[10px]"
                        >
                          {a.kind.toLowerCase()}
                        </Pill>
                        <span className="min-w-0 flex-1">
                          {a.text}
                          <span className="block text-xs text-muted-foreground">
                            {fmtDateTime(a.at)}
                          </span>
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </QueryState>
            </Panel>
          </div>

          <Panel
            className="xl:col-span-12"
            title="Tell us your hiring needs"
            description="Your answers feed the employer-survey signal of the demand score (demo: stored in this browser only)."
          >
            <DemandForm employer={employer} />
          </Panel>
        </div>
      )}
    </div>
  )
}
