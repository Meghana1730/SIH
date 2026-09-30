// Districts and institutes (GET /api/v1/districts, /api/v1/institutes).

import { apiFetch, withFallbackAsync, type Sourced } from '@/lib/api/client'
import type { District, Institute } from '@/lib/api/types'
import { OFFERINGS } from '@/lib/demo/catalog'
import { loadSnapshot } from '@/lib/demo/snapshot'

export const districtApi = {
  list: (): Promise<Sourced<District[]>> =>
    withFallbackAsync(
      () => apiFetch<District[]>('/api/v1/districts'),
      async () => (await loadSnapshot()).districts,
    ),

  institutes: (): Promise<Sourced<Institute[]>> =>
    withFallbackAsync(
      () => apiFetch<Institute[]>('/api/v1/institutes'),
      async () => {
        const districts = (await loadSnapshot()).districts
        const seen = new Map<string, Institute>()
        for (const offering of OFFERINGS) {
          if (seen.has(offering.institute.code)) continue
          seen.set(offering.institute.code, {
            id: offering.institute.code,
            code: offering.institute.code,
            name: offering.institute.name,
            institute_type: offering.institute.code.startsWith('EX-ITI') ? 'ITI' : 'PMKVY_TC',
            district_id: districts.find((d) => d.code === offering.district.code)?.id ?? '',
            is_synthetic: true,
          })
        }
        return [...seen.values()]
      },
    ),
}
