import { useId } from 'react'
import { STATUS_META, statusMeta } from '../lib/risk'

const RING_FRACTIONS = [0.24, 0.49, 0.74, 1.0]

export default function RadarCanvas({ houses, size = 320, onSelectHouse, showLegend = false }) {
  const gradientId = useId()
  const center = size / 2
  const maxRadius = size / 2 - 20
  const n = houses.length
  const sweepEdge = maxRadius * Math.sin(Math.PI / 3)
  const sweepTop = maxRadius * Math.cos(Math.PI / 3)

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <defs>
          <radialGradient id={`${gradientId}-bg`} cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#1B4332" stopOpacity="0.07" />
            <stop offset="100%" stopColor="#1B4332" stopOpacity="0" />
          </radialGradient>
          <linearGradient id={`${gradientId}-sweep`} x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#2F9E58" stopOpacity="0.4" />
            <stop offset="100%" stopColor="#2F9E58" stopOpacity="0" />
          </linearGradient>
        </defs>

        <circle cx={center} cy={center} r={maxRadius} fill={`url(#${gradientId}-bg)`} />

        <g style={{ transformOrigin: `${center}px ${center}px`, animation: 'radar-sweep 5s linear infinite' }}>
          <path
            d={`M ${center} ${center} L ${center} ${center - maxRadius} A ${maxRadius} ${maxRadius} 0 0 1 ${
              center + sweepEdge
            } ${center - sweepTop} Z`}
            fill={`url(#${gradientId}-sweep)`}
          />
        </g>

        {RING_FRACTIONS.map((f) => (
          <circle
            key={f}
            cx={center}
            cy={center}
            r={maxRadius * f}
            fill="none"
            stroke="#E4E1D8"
            strokeWidth="1"
          />
        ))}
        <circle cx={center} cy={center} r="3.5" fill="#1B4332" />

        {houses.map((house, i) => {
          const angle = (i / Math.max(n, 1)) * Math.PI * 2 - Math.PI / 2
          const radius = (house.risk_score / 100) * maxRadius
          const x = center + radius * Math.cos(angle)
          const y = center + radius * Math.sin(angle)
          const meta = statusMeta(house.risk_status)
          const dotRadius = house.risk_status === 'critical' ? 15 : 13
          const isUrgent = house.risk_status === 'critical' || house.risk_status === 'warning'

          return (
            <g
              key={house.house_id}
              transform={`translate(${x}, ${y})`}
              className={onSelectHouse ? 'cursor-pointer' : ''}
              onClick={() => onSelectHouse?.(house.house_id)}
            >
              <title>{`${house.house_name} — ${meta.label}, risk ${house.risk_score}`}</title>
              {isUrgent ? (
                <circle
                  r={dotRadius}
                  fill="none"
                  stroke={meta.color}
                  strokeWidth="2"
                  className="origin-center animate-ping"
                  opacity="0.5"
                />
              ) : null}
              <circle r={dotRadius} fill={meta.color} style={{ filter: 'drop-shadow(0 2px 5px rgba(22,34,43,0.3))' }} />
              <text textAnchor="middle" dominantBaseline="central" fontSize="12" fontWeight="700" fill="#fff">
                {(house.house_name || '?').charAt(0).toUpperCase()}
              </text>
            </g>
          )
        })}
      </svg>

      {showLegend ? (
        <div className="mt-3 flex flex-wrap justify-center gap-2">
          {Object.entries(STATUS_META).map(([key, meta]) => (
            <span
              key={key}
              className="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold"
              style={{ color: meta.color, backgroundColor: `${meta.color}14` }}
            >
              <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: meta.color }} />
              {meta.label} {meta.range}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}
