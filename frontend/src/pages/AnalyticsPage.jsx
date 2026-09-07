import { useEffect, useState } from 'react'
import { BarChart3, Skull, Wheat, Droplets, LineChart, Loader2, Inbox } from 'lucide-react'
import { api } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import TrendCard from '../components/TrendCard'

export default function AnalyticsPage() {
  const { currentFarmId, houses } = useAppStore()
  const [houseId, setHouseId] = useState('')
  const [trends, setTrends] = useState([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (houses.length > 0 && !houseId) setHouseId(houses[0].id)
  }, [houses, houseId])

  useEffect(() => {
    if (!currentFarmId || !houseId) return
    let cancelled = false
    setIsLoading(true)
    api.analytics.houseTrends(currentFarmId, houseId).then((data) => {
      if (!cancelled) {
        setTrends(data)
        setIsLoading(false)
      }
    })
    return () => {
      cancelled = true
    }
  }, [currentFarmId, houseId])

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-ai/10 text-ai">
            <BarChart3 size={20} />
          </span>
          <div>
            <h1 className="font-display text-2xl font-extrabold text-navy">Analytics</h1>
            <p className="text-sm text-navy/60">Trends for one house over time.</p>
          </div>
        </div>
        <select
          value={houseId}
          onChange={(e) => setHouseId(e.target.value)}
          className="rounded-lg border border-hairline bg-surface px-3 py-2 text-sm outline-none focus:border-forest"
        >
          {houses.map((h) => (
            <option key={h.id} value={h.id}>
              {h.name}
            </option>
          ))}
        </select>
      </div>

      {isLoading ? (
        <div className="mt-6 flex items-center justify-center gap-2 rounded-xl border border-hairline bg-surface py-16 text-sm text-navy/50 shadow-sm">
          <Loader2 size={16} className="animate-spin" />
          Loading trends...
        </div>
      ) : trends.length === 0 ? (
        <div className="mt-6 flex flex-col items-center gap-2 rounded-xl border border-hairline bg-surface py-16 text-center shadow-sm">
          <Inbox size={28} className="text-navy/20" />
          <p className="text-sm text-navy/50">No Flock Checks recorded yet for this house.</p>
        </div>
      ) : (
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <TrendCard title="Risk trend" data={trends} dataKey="risk_score" color="#16222B" Icon={LineChart} goodDirection="down" />
          <TrendCard title="Mortality trend" data={trends} dataKey="mortality" color="#C8433A" Icon={Skull} goodDirection="down" />
          <TrendCard title="Feed consumption (kg)" data={trends} dataKey="feed_kg" color="#C05A1D" Icon={Wheat} />
          <TrendCard title="Water consumption (L)" data={trends} dataKey="water_liters" color="#6C63D6" Icon={Droplets} />
        </div>
      )}
    </div>
  )
}
