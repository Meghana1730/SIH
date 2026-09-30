// District Skill Pressure map: a schematic outline of Maharashtra (not to scale, not a GIS
// boundary) with the four demo districts placed by approximate coordinates.
import { useNavigate } from 'react-router-dom'

import { mismatchTone } from '@/lib/evidence'
import type { DistrictMismatch } from '@/lib/api/types'
import { fmtScore } from '@/lib/format'

const W = 420
const H = 280
const LON = [72.5, 81.0]
const LAT = [15.5, 22.2]

function project(lon: number, lat: number): [number, number] {
  return [((lon - LON[0]) / (LON[1] - LON[0])) * W, ((LAT[1] - lat) / (LAT[1] - LAT[0])) * H]
}

// Rough outline (lon, lat), simplified by hand.
const OUTLINE: [number, number][] = [
  [72.8, 20.2], [73.6, 21.1], [74.3, 21.8], [75.8, 21.5], [76.4, 21.3], [77.3, 21.7],
  [78.4, 21.6], [79.3, 21.7], [80.4, 21.6], [80.8, 21.1], [80.5, 19.9], [79.9, 19.4],
  [79.3, 18.9], [78.4, 19.5], [77.6, 18.4], [77.3, 17.6], [76.4, 17.4], [75.7, 16.7],
  [74.5, 15.8], [73.7, 15.8], [73.3, 17.0], [73.0, 18.2], [72.8, 19.2],
]

const PLACES: Record<string, [number, number]> = {
  'MH-NASHIK': [73.79, 20.0],
  'MH-PUNE': [73.86, 18.52],
  'MH-NAGPUR': [79.09, 21.15],
  'MH-KOLHAPUR': [74.24, 16.7],
}

const TONE_COLOR = {
  danger: 'var(--danger)',
  warning: 'var(--warning)',
  success: 'var(--success)',
  neutral: 'var(--muted-foreground)',
} as const

export function MaharashtraMap({
  districts,
}: {
  districts: Pick<DistrictMismatch, 'district' | 'mismatch_score' | 'status_counts'>[]
}) {
  const navigate = useNavigate()
  const path = OUTLINE.map(([lon, lat], i) => `${i ? 'L' : 'M'}${project(lon, lat).join(',')}`).join(' ') + 'Z'
  return (
    <figure className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="group" aria-label="Schematic map of the four demo districts in Maharashtra, coloured by skill mismatch">
        <path d={path} fill="var(--accent)" stroke="var(--primary)" strokeOpacity={0.25} strokeWidth={1.5} />
        {districts.map((d) => {
          const place = PLACES[d.district.code]
          if (!place) return null
          const [x, y] = project(...place)
          const tone = mismatchTone(d.mismatch_score) as keyof typeof TONE_COLOR
          const color = TONE_COLOR[tone] ?? TONE_COLOR.neutral
          const r = 10 + Math.min(14, (d.mismatch_score ?? 0) * 5)
          const label = `${d.district.name}: mismatch ${fmtScore(d.mismatch_score)}, ${d.status_counts.UNDER_SUPPLIED ?? 0} shortage roles. Open district.`
          return (
            <g
              key={d.district.code}
              role="link"
              tabIndex={0}
              aria-label={label}
              className="cursor-pointer outline-none [&:focus-visible>circle:first-child]:stroke-[3]"
              onClick={() => navigate(`/districts/${d.district.code}`)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  navigate(`/districts/${d.district.code}`)
                }
              }}
            >
              <circle cx={x} cy={y} r={r + 6} fill={color} opacity={0.15} stroke="var(--ring)" strokeWidth={0} />
              <circle cx={x} cy={y} r={r} fill={color} opacity={0.85} />
              <text x={x} y={y + 4} textAnchor="middle" fontSize={11} fontWeight={600} fill="white">
                {fmtScore(d.mismatch_score)}
              </text>
              <text x={x + r + 8} y={y + 4} fontSize={12} fontWeight={600} fill="var(--foreground)">
                {d.district.name}
              </text>
            </g>
          )
        })}
      </svg>
      <figcaption className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-danger" /> High mismatch (2.3 or more)</span>
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-warning" /> Moderate (1.5 to 2.3)</span>
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-success" /> Low</span>
        <span className="ml-auto italic">Schematic, not to scale</span>
      </figcaption>
    </figure>
  )
}
