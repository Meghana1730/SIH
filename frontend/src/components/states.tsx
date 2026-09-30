// Loading, error and empty states, and QueryState which picks the right one for a query.
import type { UseQueryResult } from '@tanstack/react-query'
import { CloudOff, Inbox, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { errorMessage } from '@/lib/api/queries'
import { cn } from '@/lib/utils'

export function LoadingState({
  rows = 3,
  label,
  className,
}: {
  rows?: number
  label?: string
  className?: string
}) {
  const { t } = useTranslation()
  return (
    <div role="status" aria-live="polite" className={cn('space-y-3 py-2', className)}>
      <span className="sr-only">{label ?? t('common.loading')}</span>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-10 w-full" style={{ opacity: 1 - i * 0.15 }} />
      ))}
    </div>
  )
}

export function ErrorState({
  error,
  onRetry,
  className,
}: {
  error: unknown
  onRetry?: () => void
  className?: string
}) {
  const { t } = useTranslation()
  return (
    <div
      role="alert"
      className={cn(
        'flex flex-col items-center gap-3 rounded-lg border border-danger/25 bg-danger-soft px-6 py-8 text-center',
        className,
      )}
    >
      <CloudOff className="size-6 text-danger" aria-hidden />
      <div>
        <p className="font-medium text-foreground">Could not load this section</p>
        <p className="mt-1 text-sm text-muted-foreground">{errorMessage(error)}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw aria-hidden /> {t('common.retry')}
        </Button>
      )}
    </div>
  )
}

export function EmptyState({
  title,
  description,
  icon,
  action,
  className,
}: {
  title?: string
  description?: ReactNode
  icon?: ReactNode
  action?: ReactNode
  className?: string
}) {
  const { t } = useTranslation()
  return (
    <div
      className={cn(
        'flex flex-col items-center gap-2 rounded-lg border border-dashed px-6 py-10 text-center',
        className,
      )}
    >
      <div className="text-muted-foreground [&_svg]:size-6">{icon ?? <Inbox aria-hidden />}</div>
      <p className="font-medium">{title ?? t('common.noData')}</p>
      {description && <p className="max-w-md text-sm text-muted-foreground">{description}</p>}
      {action}
    </div>
  )
}

/**
 * Renders loading / error / empty for a query, and children(data) when there is data.
 * `isEmpty` decides what counts as empty (default: an empty array).
 */
export function QueryState<T>({
  query,
  children,
  isEmpty,
  empty,
  loadingRows,
}: {
  query: UseQueryResult<T>
  children: (data: T) => ReactNode
  isEmpty?: (data: T) => boolean
  empty?: ReactNode
  loadingRows?: number
}) {
  if (query.isPending) return <LoadingState rows={loadingRows} />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />
  const data = query.data
  const emptyCheck = isEmpty ?? ((d: T) => Array.isArray(d) && d.length === 0)
  if (data === null || data === undefined || emptyCheck(data)) return <>{empty ?? <EmptyState />}</>
  return <>{children(data)}</>
}
