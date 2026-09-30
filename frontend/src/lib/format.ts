// Number and label formatting shared by all pages.

import type { SectorCode } from '@/lib/api/types'

const integer = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
const oneDecimal = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 1 })

export function fmtInt(value: number | null | undefined): string {
  return value === null || value === undefined || Number.isNaN(value) ? '-' : integer.format(value)
}

export function fmtScore(value: number | null | undefined): string {
  return value === null || value === undefined ? '-' : oneDecimal.format(value)
}

export function fmtRatio(value: number | null | undefined): string {
  return value === null || value === undefined ? '-' : value.toFixed(2)
}

export function fmtPct(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? '-' : `${(value * 100).toFixed(digits)}%`
}

export function fmtDate(value: string | null | undefined): string {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

export const SECTOR_LABELS: Record<SectorCode, string> = {
  ELECTRICAL: 'Electrical',
  EV: 'Electric Vehicles',
  SOLAR_PV: 'Solar PV',
}

export function sectorLabel(code: string | null | undefined): string {
  return code ? (SECTOR_LABELS[code as SectorCode] ?? code) : '-'
}

/** "MH-NASHIK" -> "Nashik" when no name is at hand. */
export function districtName(code: string): string {
  const name = code.replace(/^MH-/, '').toLowerCase()
  return name.charAt(0).toUpperCase() + name.slice(1)
}

/** Demand-score band used for colour: >= 70 high, >= 45 medium, else low. */
export function demandLevel(score: number | null | undefined): 'high' | 'medium' | 'low' {
  if (score === null || score === undefined) return 'low'
  if (score >= 70) return 'high'
  if (score >= 45) return 'medium'
  return 'low'
}

export function bandLabel(band: number): string {
  return ['Not taught', 'Basic', 'Intermediate', 'Advanced'][band] ?? '-'
}
