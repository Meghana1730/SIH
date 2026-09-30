// Global filters set from the top bar (sector, district, quarter) and read by every page.
import { createContext, useContext } from 'react'

import type { SectorCode } from '@/lib/api/types'

export type GlobalFilters = {
  sector: SectorCode | 'ALL'
  district: string | 'ALL'
  /** null = the latest quarter of the current analytics run */
  quarter: string | null
}

export type FiltersState = GlobalFilters & {
  setSector: (sector: GlobalFilters['sector']) => void
  setDistrict: (district: string) => void
  setQuarter: (quarter: string | null) => void
  /** Filters in the shape the API services take. */
  api: { sector?: string; district?: string; quarter?: string }
}

export const FiltersContext = createContext<FiltersState | null>(null)

export function useFilters(): FiltersState {
  const filters = useContext(FiltersContext)
  if (!filters) throw new Error('useFilters must be used inside <FiltersProvider>')
  return filters
}

export const SECTORS: { code: SectorCode; label: string }[] = [
  { code: 'ELECTRICAL', label: 'Electrical' },
  { code: 'EV', label: 'Electric Vehicles' },
  { code: 'SOLAR_PV', label: 'Solar PV' },
]
