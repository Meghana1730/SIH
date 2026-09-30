// Page title and breadcrumb label for each route (react-router `handle`).
import { useEffect } from 'react'
import { useMatches, type Params } from 'react-router-dom'

export type RouteHandle = {
  /** i18n key of the page title shown in the top bar */
  titleKey?: string
  /** breadcrumb label; a function receives the route params */
  crumb?: string | ((params: Params) => string)
}

export type Crumb = { label: string; to: string }

export function useRouteMeta(): { titleKey: string | undefined; crumbs: Crumb[] } {
  const matches = useMatches()
  let titleKey: string | undefined
  const crumbs: Crumb[] = []
  for (const match of matches) {
    const handle = match.handle as RouteHandle | undefined
    if (!handle) continue
    if (handle.titleKey) titleKey = handle.titleKey
    if (handle.crumb) {
      const label = typeof handle.crumb === 'function' ? handle.crumb(match.params) : handle.crumb
      crumbs.push({ label, to: match.pathname })
    }
  }
  return { titleKey, crumbs }
}

/** Sets the browser tab title. */
export function useDocumentTitle(title: string | undefined) {
  useEffect(() => {
    document.title = title ? `${title} · InnovProcure` : 'InnovProcure'
  }, [title])
}
