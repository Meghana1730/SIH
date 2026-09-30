// Sign-in screen (rendered without the app shell): "Enter demo" or email + password.
import {
  Activity,
  ArrowRight,
  FileCheck2,
  FlaskConical,
  KeyRound,
  LoaderCircle,
  MapPin,
  Radar,
  Scale,
  UserRound,
} from 'lucide-react'
import { useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { toast } from 'sonner'

import { ROLE_LABELS, useSession } from '@/app/session'
import { Pill } from '@/components/badges'
import { useDocumentTitle } from '@/components/layout/route-meta'
import { Logo } from '@/components/layout/Sidebar'
import { LoadingState } from '@/components/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { errorMessage } from '@/lib/api/queries'
import { DISTRICTS } from '@/lib/demo/catalog'
import { DEMO_ACCOUNTS, DEMO_LOGIN } from '@/lib/demo/config'

const VALUE_POINTS: { icon: ReactNode; title: string; text: string }[] = [
  {
    icon: <Radar aria-hidden />,
    title: 'Job-ad + employer-survey demand signals',
    text: 'Demand per role and skill, district by district, with the evidence behind each score.',
  },
  {
    icon: <Scale aria-hidden />,
    title: 'Training supply vs estimated openings per district',
    text: 'Where trained candidates fall short of, or exceed, the openings employers are likely to have.',
  },
  {
    icon: <FileCheck2 aria-hidden />,
    title: 'Evidence-backed course recommendations',
    text: 'Concrete changes for institutes, validated by employers and tracked in district plans.',
  },
]

type Pending = 'demo' | 'login' | null

export default function LoginPage() {
  const { t } = useTranslation()
  const session = useSession()
  const location = useLocation()
  useDocumentTitle(t('pages.login'))

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<Pending>(null)
  const passwordRef = useRef<HTMLInputElement>(null)

  const requested = (location.state as { from?: string } | null)?.from
  const from = requested && !requested.startsWith('/login') ? requested : '/dashboard'

  // Once a session exists (already signed in, or just signed in) go to the requested page.
  if (session.user) return <Navigate to={from} replace />
  if (!session.ready) return <LoadingState className="p-8" label="Checking your session" />

  async function enterDemo() {
    setError(null)
    setPending('demo')
    try {
      const mode = await session.enterDemo()
      if (mode === 'api') toast.success('Signed in to the live API with the demo account')
      else toast.info('Offline demo mode: showing built-in demo data')
    } catch (e) {
      setError(errorMessage(e))
      setPending(null)
    }
  }

  async function signIn(address: string, secret: string) {
    setError(null)
    setPending('login')
    try {
      await session.login(address, secret)
      toast.success('Signed in to the InnovProcure API')
    } catch (e) {
      setError(errorMessage(e))
      setPending(null)
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending) return
    void signIn(email.trim(), password)
  }

  function pickAccount(address: string) {
    setEmail(address)
    setError(null)
    if (DEMO_LOGIN.password) void signIn(address, DEMO_LOGIN.password)
    else passwordRef.current?.focus()
  }

  const busy = pending !== null
  const statusText =
    pending === 'demo' ? 'Entering the demo...' : pending === 'login' ? 'Signing in...' : ''

  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      {/* ------------------------------------------------------------ hero */}
      <aside className="relative flex flex-col justify-between gap-10 overflow-hidden bg-sidebar px-6 py-8 text-sidebar-foreground sm:px-10 lg:px-12 lg:py-12">
        <div
          aria-hidden
          className="pointer-events-none absolute -top-32 -right-32 size-96 rounded-full bg-sidebar-accent/40 blur-3xl"
        />
        <div className="relative">
          <Logo />
        </div>

        <div className="animate-in-up relative max-w-xl space-y-6">
          <p className="text-xs font-semibold tracking-wider text-sidebar-ring uppercase">
            Electrical · EV · Solar PV · Maharashtra
          </p>
          <h1 className="text-3xl leading-tight font-semibold tracking-tight text-sidebar-primary xl:text-4xl">
            {t('login.title')}
          </h1>
          <p className="text-base leading-relaxed text-sidebar-foreground/85">
            {t('login.subtitle')}
          </p>

          <ul className="space-y-4">
            {VALUE_POINTS.map((point) => (
              <li key={point.title} className="flex gap-3">
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-sidebar-accent text-sidebar-primary [&_svg]:size-4.5">
                  {point.icon}
                </span>
                <div>
                  <p className="font-medium text-sidebar-primary">{point.title}</p>
                  <p className="text-sm text-sidebar-foreground/75">{point.text}</p>
                </div>
              </li>
            ))}
          </ul>

          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="inline-flex items-center gap-1.5 text-sidebar-foreground/75">
              <MapPin className="size-4" aria-hidden /> Demo districts:
            </span>
            {DISTRICTS.map((d) => (
              <span
                key={d.code}
                className="rounded-md border border-sidebar-border bg-sidebar-accent/50 px-2 py-0.5 text-xs font-medium text-sidebar-primary"
              >
                {d.name}
              </span>
            ))}
          </div>
        </div>

        <p className="relative flex max-w-xl gap-2.5 rounded-lg border border-sidebar-border bg-sidebar-accent/40 px-4 py-3 text-sm text-sidebar-foreground">
          <FlaskConical className="mt-0.5 size-4 shrink-0 text-sidebar-ring" aria-hidden />
          <span>{t('login.demoNote')}</span>
        </p>
      </aside>

      {/* ------------------------------------------------------------ sign-in */}
      <main className="flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="animate-in-up w-full max-w-md space-y-6">
          <section
            aria-labelledby="signin-heading"
            className="space-y-6 rounded-xl border bg-card p-6 shadow-sm sm:p-8"
          >
            <div className="space-y-1.5">
              <h2 id="signin-heading" className="text-xl font-semibold tracking-tight">
                {t('pages.login')}
              </h2>
              <p className="text-sm text-muted-foreground">
                Explore the prototype straight away, or sign in to the InnovProcure API with an
                account.
              </p>
            </div>

            <div className="space-y-2">
              <Button
                type="button"
                size="lg"
                className="h-11 w-full text-base"
                onClick={enterDemo}
                disabled={busy}
              >
                {pending === 'demo' ? (
                  <LoaderCircle className="animate-spin" aria-hidden />
                ) : (
                  <ArrowRight aria-hidden />
                )}
                {pending === 'demo' ? 'Entering demo...' : t('login.enterDemo')}
              </Button>
              <p className="text-xs text-muted-foreground">
                Uses the live API when a demo account is configured; otherwise runs offline with
                built-in demo data (clearly labelled).
              </p>
            </div>

            <div className="flex items-center gap-3 text-xs font-medium tracking-wide text-muted-foreground uppercase">
              <span className="h-px flex-1 bg-border" aria-hidden />
              or sign in
              <span className="h-px flex-1 bg-border" aria-hidden />
            </div>

            <form className="space-y-4" onSubmit={onSubmit}>
              <div className="space-y-2">
                <Label htmlFor="login-email">{t('login.email')}</Label>
                <Input
                  id="login-email"
                  type="email"
                  autoComplete="username"
                  required
                  className="h-10"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  aria-invalid={error ? true : undefined}
                  aria-describedby={error ? 'login-error' : undefined}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="login-password">{t('login.password')}</Label>
                <Input
                  id="login-password"
                  ref={passwordRef}
                  type="password"
                  autoComplete="current-password"
                  required
                  className="h-10"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  aria-invalid={error ? true : undefined}
                  aria-describedby={error ? 'login-error' : undefined}
                />
              </div>

              {error && (
                <p
                  id="login-error"
                  role="alert"
                  className="rounded-lg border border-danger/25 bg-danger-soft px-3 py-2 text-sm text-danger"
                >
                  {error}
                </p>
              )}

              <Button
                type="submit"
                variant="outline"
                size="lg"
                className="h-10 w-full"
                disabled={busy}
              >
                {pending === 'login' ? (
                  <LoaderCircle className="animate-spin" aria-hidden />
                ) : (
                  <KeyRound aria-hidden />
                )}
                {pending === 'login' ? 'Signing in...' : t('login.signIn')}
              </Button>
              <p className="sr-only" role="status" aria-live="polite">
                {statusText}
              </p>
            </form>
          </section>

          {/* Local development only: all local demo accounts share one password. A deployed
              site has one public read-only demo account (used by "Enter demo"); clicking the
              others with its password would only lock them out. */}
          {import.meta.env.DEV && (
            <section
              aria-labelledby="demo-accounts-heading"
              className="space-y-3 rounded-xl border bg-card p-5 shadow-xs"
            >
              <div>
                <h2 id="demo-accounts-heading" className="text-sm font-semibold">
                  {t('login.demoAccounts')}
                </h2>
                <p className="text-xs text-muted-foreground">
                  {DEMO_LOGIN.password
                    ? 'Click an account to sign in with the local demo password.'
                    : 'Click an account to fill in its email address.'}
                </p>
              </div>
              <ul className="divide-y rounded-lg border">
                {DEMO_ACCOUNTS.map((account) => (
                  <li key={account.email}>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => pickAccount(account.email)}
                      className="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-muted focus-visible:outline-2 disabled:opacity-60"
                    >
                      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-accent text-primary">
                        <UserRound className="size-4" aria-hidden />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{account.label}</span>
                        <span className="block truncate font-mono text-xs text-muted-foreground">
                          {account.email}
                        </span>
                      </span>
                      <Pill tone={account.role === 'admin' ? 'primary' : 'neutral'}>
                        {ROLE_LABELS[account.role]}
                      </Pill>
                    </button>
                  </li>
                ))}
              </ul>
              <p className="text-xs text-muted-foreground">
                Passwords are set locally with{' '}
                <code className="rounded bg-muted px-1 py-0.5 font-mono text-[11px] text-foreground">
                  python -m app.cli.demo_users
                </code>
                ; they are never stored in the code.
              </p>
            </section>
          )}

          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <Link
              to="/status"
              className="inline-flex items-center gap-1.5 rounded font-medium text-primary hover:underline focus-visible:outline-2"
            >
              <Activity className="size-3.5" aria-hidden /> System status
            </Link>
            <span>Prototype · synthetic demo data · not official statistics</span>
          </div>
        </div>
      </main>
    </div>
  )
}
