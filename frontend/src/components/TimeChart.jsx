import { Area, AreaChart, Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { PERIOD_LABELS } from '../lib/checkLabels'

const shortDate = (iso) => new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' })

function ChartTooltip({ active, payload, label, unit, valueLabel }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload
  return (
    <div className="rounded-lg border border-hairline bg-surface px-3 py-2 text-xs shadow-md">
      <p className="text-muted">
        {new Date(label).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
        {point.period ? ` · ${PERIOD_LABELS[point.period] || point.period}` : ''}
      </p>
      <p className="mt-0.5 flex items-center gap-1.5 font-semibold text-navy">
        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: payload[0].color }} />
        {valueLabel}: {payload[0].value}
        {unit ? ` ${unit}` : ''}
      </p>
    </div>
  )
}

// One measure over time for one house - a single series, so no legend (the
// card title names it). kind="bar" for counts per check (dead birds),
// "area" for continuous readings. `thresholds` draws labelled dashed lines
// (e.g. the Watch/Warning/Critical risk bands).
export default function TimeChart({ data, dataKey, kind = 'area', color, unit, valueLabel, height = 180, yDomain, thresholds = [] }) {
  const gradientId = `time-grad-${dataKey}`
  const axisProps = {
    tick: { fill: 'var(--color-muted)', fontSize: 11 },
    tickLine: false,
    axisLine: false,
  }
  const common = (
    <>
      <CartesianGrid vertical={false} stroke="var(--color-hairline)" strokeDasharray="3 3" />
      <XAxis dataKey="recorded_at" tickFormatter={shortDate} minTickGap={28} {...axisProps} />
      <YAxis width={32} domain={yDomain || [0, 'auto']} allowDecimals={false} {...axisProps} />
      {thresholds.map((t) => (
        <ReferenceLine
          key={t.value}
          y={t.value}
          stroke={t.color}
          strokeDasharray="4 4"
          strokeOpacity={0.6}
          label={{ value: t.label, position: 'insideTopRight', fill: 'var(--color-muted)', fontSize: 10 }}
        />
      ))}
      <Tooltip
        content={<ChartTooltip unit={unit} valueLabel={valueLabel} />}
        cursor={kind === 'bar' ? { fill: 'var(--color-hairline)', fillOpacity: 0.4 } : { stroke: 'var(--color-muted)', strokeDasharray: '3 3' }}
      />
    </>
  )

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        {kind === 'bar' ? (
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            {common}
            <Bar dataKey={dataKey} fill={color} radius={[4, 4, 0, 0]} maxBarSize={18} />
          </BarChart>
        ) : (
          <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.25} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            {common}
            <Area
              type="monotone"
              dataKey={dataKey}
              stroke={color}
              strokeWidth={2}
              fill={`url(#${gradientId})`}
              connectNulls
              dot={false}
              activeDot={{ r: 4, stroke: 'var(--color-surface)', strokeWidth: 2 }}
            />
          </AreaChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}
