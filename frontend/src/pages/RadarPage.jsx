import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Radar, Loader2, Building2, ChevronRight, AlertTriangle } from 'lucide-react'
import { api } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import RadarCanvas from '../components/RadarCanvas'
import StatusBadge from '../components/StatusBadge'
import { statusMeta } from '../lib/risk'

export default function RadarPage() {
  const { currentFarmId } = useAppStore()
  const [houses, setHouses] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    if (!currentFarmId) return
    let cancelled = false
    api.analytics.compareHouses(currentFarmId).then((data) => {
      if (!cancelled) {
        setHouses(data)
        setIsLoading(false)
      }
    })
    return () => {
      cancelled = true
    }
  }, [currentFarmId])

  const checked = houses.filter((h) => h.risk_score !== null)

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-ai/10 text-ai">
          <Radar size={20} />
        </span>
        <div>
          <h1 className="font-display text-2xl font-extrabold text-navy">AI Health Radar</h1>
          <p className="text-sm text-navy/60">Which poultry house should I inspect first?</p>
        </div>
      </div>

      <div className="mt-6 flex flex-col gap-6 lg:flex-row">
        <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-hairline bg-surface p-6 shadow-sm">
          {isLoading ? (
            <div className="flex items-center gap-2 py-16 text-sm text-navy/50">
              <Loader2 size={16} className="animate-spin" />
              Loading radar...
            </div>
          ) : checked.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-16 text-center">
              <Radar size={28} className="text-navy/20" />
              <p className="text-sm text-navy/50">No Flock Checks recorded yet.</p>
            </div>
          ) : (
            <RadarCanvas houses={checked} size={360} showLegend onSelectHouse={(id) => navigate(`/houses/${id}`)} />
          )}
        </div>

        <div className="w-full rounded-xl border border-hairline bg-surface p-5 shadow-sm lg:w-80">
          <h2 className="text-sm font-bold uppercase tracking-wide text-navy/50">Priority Queue</h2>
          <ol className="mt-3 space-y-1.5">
            {houses.map((house, i) => {
              const meta = statusMeta(house.risk_status)
              const inspectNow = i === 0 && house.risk_status !== 'normal'
              return (
                <li key={house.house_id}>
                  <button
                    type="button"
                    onClick={() => navigate(`/houses/${house.house_id}`)}
                    className="flex w-full items-center gap-3 rounded-lg px-2 py-2.5 text-left transition-colors hover:bg-forest/5"
                  >
                    <span className="w-5 shrink-0 font-display text-xs font-bold text-navy/30">
                      {String(i + 1).padStart(2, '0')}
                    </span>
                    <span
                      className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
                      style={{ backgroundColor: `${meta.color}14`, color: meta.color }}
                    >
                      <Building2 size={16} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-navy">{house.house_name}</span>
                      <span className="mt-0.5 flex items-center gap-1">
                        <StatusBadge status={house.risk_status} size="sm" pill />
                        {inspectNow ? (
                          <span className="flex items-center gap-0.5 text-xs font-semibold text-critical">
                            <AlertTriangle size={11} />
                            Inspect now
                          </span>
                        ) : null}
                      </span>
                    </span>
                    <span className="font-display text-lg font-extrabold" style={{ color: meta.color }}>
                      {house.risk_score ?? '—'}
                    </span>
                    <ChevronRight size={16} className="shrink-0 text-navy/25" />
                  </button>
                </li>
              )
            })}
          </ol>
        </div>
      </div>
    </div>
  )
}
