// Fallback for unknown routes inside the app shell.
import { ArrowLeft, Compass } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'

import { EmptyState } from '@/components/states'
import { Button } from '@/components/ui/button'

export default function NotFoundPage() {
  const location = useLocation()
  return (
    <div className="animate-in-up mx-auto max-w-2xl py-10">
      <EmptyState
        className="bg-card py-14"
        icon={<Compass aria-hidden />}
        title="Page not found"
        description={
          <>
            There is no page at{' '}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs text-foreground">
              {location.pathname}
            </code>{' '}
            in this prototype. It may have moved, or the link may be mistyped.
          </>
        }
        action={
          <div className="mt-3 flex flex-wrap justify-center gap-2">
            <Button asChild>
              <Link to="/dashboard">
                <ArrowLeft aria-hidden /> Back to the overview
              </Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/help">How InnovProcure works</Link>
            </Button>
          </div>
        }
      />
    </div>
  )
}
