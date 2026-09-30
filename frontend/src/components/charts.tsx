// Charts (Recharts). Each chart has an accessible text summary (aria-label + sr-only table
// caption) so the numbers are not locked inside the SVG.
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { fmtInt } from '@/lib/format'

const SERIES_COLORS = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--chart-4)',
  'var(--chart-5)',
  'oklch(0.55 0.12 320)',
  'oklch(0.45 0.05 260)',
]

const axis = { fontSize: 12, fill: 'var(--muted-foreground)' }
const tooltipStyle = {
  borderRadius: 8,
  border: '1px solid var(--border)',
  fontSize: 12,
  boxShadow: '0 4px 12px rgb(0 0 0 / 0.06)',
}

export type Series = { key: string; label: string }

/** Demand over quarters: one line per series. data = [{ quarter, [series.key]: value }] */
export function DemandChart({
  data,
  series,
  height = 260,
  yLabel = 'Demand score',
  domain = [0, 100],
}: {
  data: Record<string, string | number | null>[]
  series: Series[]
  height?: number
  yLabel?: string
  domain?: [number, number | 'auto']
}) {
  const summary = series
    .map((s) => {
      const values = data.map((d) => d[s.key]).filter((v): v is number => typeof v === 'number')
      return values.length
        ? `${s.label}: ${values[0].toFixed(0)} to ${values[values.length - 1].toFixed(0)}`
        : ''
    })
    .filter(Boolean)
    .join('; ')
  return (
    <figure aria-label={`${yLabel} by quarter. ${summary}`} className="w-full">
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -8 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="quarter" tick={axis} tickLine={false} axisLine={false} />
          <YAxis tick={axis} tickLine={false} axisLine={false} domain={domain} width={44} />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 12 }} iconType="circle" />
          {series.map((s, i) => (
            <Line
              key={s.key}
              type="monotone"
              dataKey={s.key}
              name={s.label}
              stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
              strokeWidth={2.25}
              dot={{ r: 3 }}
              activeDot={{ r: 5 }}
              connectNulls
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <figcaption className="sr-only">{summary}</figcaption>
    </figure>
  )
}

/** Trained people per year by category (vertical bars). */
export function SupplyChart({
  data,
  height = 240,
  label = 'Trained per year',
}: {
  data: { name: string; value: number }[]
  height?: number
  label?: string
}) {
  return (
    <figure aria-label={`${label}: ${data.map((d) => `${d.name} ${fmtInt(d.value)}`).join(', ')}`}>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" tick={axis} tickLine={false} axisLine={false} interval={0} />
          <YAxis tick={axis} tickLine={false} axisLine={false} width={44} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => [fmtInt(Number(v)), label]} />
          <Bar
            dataKey="value"
            name={label}
            fill="var(--chart-2)"
            radius={[4, 4, 0, 0]}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}

/**
 * Industry -> training gap: estimated openings vs trained supply per role (horizontal bars).
 * Openings are a modelling estimate (postings / coverage factor), not an official figure.
 */
export function GapChart({
  data,
  height,
}: {
  data: { name: string; openings: number; supply: number }[]
  height?: number
}) {
  const h = height ?? Math.max(180, data.length * 44 + 40)
  return (
    <figure
      aria-label={`Estimated openings vs trained supply per year: ${data
        .map((d) => `${d.name}: ${fmtInt(d.openings)} openings, ${fmtInt(d.supply)} trained`)
        .join('; ')}`}
    >
      <ResponsiveContainer width="100%" height={h}>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ top: 4, right: 16, bottom: 0, left: 8 }}
          barGap={2}
        >
          <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tick={axis} tickLine={false} axisLine={false} />
          <YAxis
            type="category"
            dataKey="name"
            tick={axis}
            tickLine={false}
            axisLine={false}
            width={170}
          />
          <Tooltip contentStyle={tooltipStyle} formatter={(v, name) => [fmtInt(Number(v)), name]} />
          <Legend wrapperStyle={{ fontSize: 12 }} iconType="circle" />
          <Bar
            dataKey="openings"
            name="Est. openings / yr"
            fill="var(--chart-1)"
            radius={[0, 4, 4, 0]}
            barSize={12}
            isAnimationActive={false}
          />
          <Bar
            dataKey="supply"
            name="Trained / yr"
            fill="var(--chart-3)"
            radius={[0, 4, 4, 0]}
            barSize={12}
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}
