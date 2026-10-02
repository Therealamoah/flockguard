import { useState } from 'react'
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { ChartBar, ChartPie } from 'lucide-react'

function SliceTooltip({ active, payload, total }) {
  if (!active || !payload?.length) return null
  const item = payload[0].payload
  return (
    <div className="rounded-lg border border-hairline bg-surface px-3 py-2 text-xs shadow-md">
      <p className="flex items-center gap-1.5 font-semibold text-navy">
        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} />
        {item.label}
      </p>
      <p className="mt-0.5 text-secondary">
        {item.value} ({Math.round((item.value / total) * 100)}%)
      </p>
    </div>
  )
}

// Part-to-whole card with a Pie / Bars switch. `items` keep the caller's
// FIXED order (never re-sorted by size) so each slice's color and position
// stay tied to what it is. The legend always shows the label, count and
// share - identity never relies on color alone, and it carries the values
// for the lighter colors that sit under 3:1 contrast on the light surface.
export default function BreakdownCard({ title, subtitle, items, unitLabel, emptyText }) {
  const [view, setView] = useState('pie')
  const shown = items.filter((i) => i.value > 0)
  const total = shown.reduce((sum, i) => sum + i.value, 0)
  const max = Math.max(...shown.map((i) => i.value), 1)

  return (
    <div className="rounded-xl border border-hairline bg-surface p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-navy">{title}</h2>
          {subtitle ? <p className="mt-0.5 text-xs text-secondary">{subtitle}</p> : null}
        </div>
        <div className="flex shrink-0 gap-1 rounded-lg border border-hairline p-0.5" role="group" aria-label="Chart type">
          {[
            ['pie', ChartPie, 'Pie'],
            ['bars', ChartBar, 'Bars'],
          ].map(([key, Icon, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setView(key)}
              aria-pressed={view === key}
              className={[
                'flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold transition-colors',
                view === key ? 'bg-forest text-white' : 'text-secondary hover:bg-forest/5',
              ].join(' ')}
            >
              <Icon size={13} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {total === 0 ? (
        <p className="py-10 text-center text-sm text-secondary">{emptyText}</p>
      ) : view === 'pie' ? (
        <div className="mt-4 flex flex-col items-center gap-4 sm:flex-row">
          <div className="relative h-44 w-44 shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={shown}
                  dataKey="value"
                  nameKey="label"
                  innerRadius="62%"
                  outerRadius="100%"
                  startAngle={90}
                  endAngle={-270}
                  stroke="var(--color-surface)"
                  strokeWidth={2}
                  isAnimationActive={false}
                >
                  {shown.map((item) => (
                    <Cell key={item.key} fill={item.color} />
                  ))}
                </Pie>
                <Tooltip content={<SliceTooltip total={total} />} />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="font-display text-2xl font-extrabold text-navy">{total}</span>
              <span className="text-[11px] text-muted">{unitLabel}</span>
            </div>
          </div>
          <ul className="w-full space-y-1.5 text-sm">
            {shown.map((item) => (
              <li key={item.key} className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: item.color }} />
                <span className="min-w-0 flex-1 truncate text-secondary">{item.label}</span>
                <span className="font-semibold tabular-nums text-navy">{item.value}</span>
                <span className="w-10 text-right text-xs tabular-nums text-muted">
                  {Math.round((item.value / total) * 100)}%
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <ul className="mt-4 space-y-2.5">
          {shown.map((item) => (
            <li key={item.key} title={`${item.label}: ${item.value}`}>
              <div className="flex items-center justify-between text-sm">
                <span className="truncate text-secondary">{item.label}</span>
                <span className="ml-2 shrink-0 font-semibold tabular-nums text-navy">
                  {item.value} <span className="text-xs font-normal text-muted">({Math.round((item.value / total) * 100)}%)</span>
                </span>
              </div>
              <div className="mt-1 h-2 rounded-full bg-hairline/60">
                <div className="h-2 rounded-full" style={{ width: `${(item.value / max) * 100}%`, backgroundColor: item.color }} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
