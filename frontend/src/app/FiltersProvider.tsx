import { useMemo, useState, type ReactNode } from 'react'

import { FiltersContext, type FiltersState, type GlobalFilters } from '@/app/filters'

const KEY = 'kaushalsetu.filters'

function initial(): GlobalFilters {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) ?? 'null') as GlobalFilters | null
    if (saved)
      return {
        sector: saved.sector ?? 'ALL',
        district: saved.district ?? 'ALL',
        quarter: saved.quarter ?? null,
      }
  } catch {
    // Ignore unreadable or blocked storage.
  }
  return { sector: 'ALL', district: 'ALL', quarter: null }
}

export function FiltersProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<GlobalFilters>(initial)

  const value = useMemo<FiltersState>(() => {
    const update = (change: Partial<GlobalFilters>) =>
      setFilters((current) => {
        const next = { ...current, ...change }
        try {
          localStorage.setItem(KEY, JSON.stringify(next))
        } catch {
          // Not remembered; fine.
        }
        return next
      })
    return {
      ...filters,
      setSector: (sector) => update({ sector }),
      setDistrict: (district) => update({ district }),
      setQuarter: (quarter) => update({ quarter }),
      api: {
        sector: filters.sector === 'ALL' ? undefined : filters.sector,
        district: filters.district === 'ALL' ? undefined : filters.district,
        quarter: filters.quarter ?? undefined,
      },
    }
  }, [filters])

  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>
}
