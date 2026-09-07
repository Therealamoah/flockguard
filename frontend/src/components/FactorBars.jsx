import { statusFromScore, statusMeta } from '../lib/risk'

// Each risk factor's `points` already sits on the same 0-100 scale as the
// overall score, so it doubles directly as this factor's bar-fill percent.
export default function FactorBars({ factors, emptyMessage = 'No risk factors detected — everything looks normal.' }) {
  if (!factors || factors.length === 0) {
    return <p className="text-sm text-navy/60">{emptyMessage}</p>
  }

  return (
    <div className="space-y-3">
      {factors.map((f) => {
        const pct = Math.min(Math.round(f.points), 100)
        const color = statusMeta(statusFromScore(pct)).color
        return (
          <div key={f.key} className="flex items-center gap-3">
            <span className="w-40 shrink-0 text-sm text-navy/70">{f.label}</span>
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-hairline">
              <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
            </div>
            <span className="w-10 shrink-0 text-right text-sm font-semibold" style={{ color }}>
              {pct}%
            </span>
          </div>
        )
      })}
    </div>
  )
}
