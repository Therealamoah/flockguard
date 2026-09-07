import { statusMeta } from '../lib/risk'

export default function StatusBadge({ status, score, size = 'md', pill = false }) {
  const meta = statusMeta(status)
  const textSize = size === 'sm' ? 'text-xs' : 'text-sm'

  if (pill) {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-bold ${textSize}`}
        style={{ color: meta.color, backgroundColor: `${meta.color}1A` }}
      >
        <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: meta.color }} />
        {meta.label}
      </span>
    )
  }

  return (
    <span className={`inline-flex items-center gap-1.5 font-semibold ${textSize}`} style={{ color: meta.color }}>
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: meta.color }} />
      {meta.label}
      {score !== undefined ? <span className="text-navy/40">— {score}</span> : null}
    </span>
  )
}
