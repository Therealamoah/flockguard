import { AreaChart, Area, ResponsiveContainer, Tooltip, XAxis, CartesianGrid } from 'recharts'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-hairline bg-surface px-3 py-2 text-xs shadow-md">
      <p className="text-navy/50">
        {new Date(label).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
      </p>
      <p className="mt-0.5 font-semibold text-navy">{payload[0].value}</p>
    </div>
  )
}

// goodDirection: 'up' | 'down' | null - which direction of change reads as
// improvement for this metric, so the delta badge can be colored meaningfully.
export default function TrendCard({ title, data, dataKey, color, Icon, goodDirection = null }) {
  const values = data.map((d) => d[dataKey]).filter((v) => v != null)
  const latest = values.length ? values[values.length - 1] : null
  const first = values.length ? values[0] : null
  const delta = latest != null && first != null ? latest - first : null
  const gradientId = `trend-grad-${dataKey}`

  let deltaColor = 'text-navy/40'
  if (delta && goodDirection) {
    const isGood = (goodDirection === 'up' && delta > 0) || (goodDirection === 'down' && delta < 0)
    deltaColor = isGood ? 'text-normal' : 'text-critical'
  }
  const TrendIcon = !delta ? Minus : delta > 0 ? TrendingUp : TrendingDown

  return (
    <div className="rounded-xl border border-hairline bg-surface p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {Icon ? (
            <span
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
              style={{ backgroundColor: `${color}14`, color }}
            >
              <Icon size={14} />
            </span>
          ) : null}
          <p className="text-xs font-semibold text-navy/60">{title}</p>
        </div>
        {latest != null ? (
          <div className="flex items-center gap-2">
            <span className="font-display text-base font-extrabold text-navy">{latest}</span>
            {delta != null ? (
              <span className={`flex items-center gap-0.5 text-xs font-semibold ${deltaColor}`}>
                <TrendIcon size={12} />
                {Math.abs(delta)}
              </span>
            ) : null}
          </div>
        ) : null}
      </div>
      <div className="mt-2 h-28">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="#E4E1D8" strokeDasharray="3 3" />
            <XAxis dataKey="recorded_at" hide />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey={dataKey}
              stroke={color}
              strokeWidth={2}
              fill={`url(#${gradientId})`}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
