import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bird, Building2, ChevronRight, Loader2, Search, Weight } from 'lucide-react'
import { api } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import StatCard from '../components/StatCard'
import StatusBadge from '../components/StatusBadge'
import { statusMeta } from '../lib/risk'
import { ageLabel, assignFlockCodes } from '../lib/format'

const TYPE_COLOR = { broiler: '#1B4332', layer: '#6C63D6', breeder: '#B3811A' }

export default function FlocksPage() {
  const { currentFarmId, houses } = useAppStore()
  const navigate = useNavigate()
  const [flocks, setFlocks] = useState([])
  const [riskByHouse, setRiskByHouse] = useState({})
  const [birdsByHouse, setBirdsByHouse] = useState({})
  const [isLoading, setIsLoading] = useState(true)
  const [query, setQuery] = useState('')

  useEffect(() => {
    if (!currentFarmId || houses.length === 0) {
      setIsLoading(false)
      return
    }
    let cancelled = false

    async function load() {
      const [compare, flocksByHouse, checksByHouse] = await Promise.all([
        api.analytics.compareHouses(currentFarmId),
        Promise.all(
          houses.map((h) =>
            api.flocks.list(currentFarmId, h.id).then((list) => list.map((f) => ({ ...f, house: h })))
          )
        ),
        Promise.all(
          houses.map((h) =>
            api.flockChecks
              .list(currentFarmId, h.id)
              .then((checks) => ({ houseId: h.id, latest: checks[0] }))
              .catch(() => ({ houseId: h.id, latest: null }))
          )
        ),
      ])
      if (cancelled) return

      const riskMap = {}
      for (const h of compare) riskMap[h.house_id] = h
      const birdsMap = {}
      for (const { houseId, latest } of checksByHouse) {
        if (latest?.bird_count != null) birdsMap[houseId] = latest.bird_count
      }
      setRiskByHouse(riskMap)
      setBirdsByHouse(birdsMap)
      setFlocks(flocksByHouse.flat())
      setIsLoading(false)
    }

    load()
    return () => {
      cancelled = true
    }
  }, [currentFarmId, houses])

  const flockCodes = assignFlockCodes(flocks)

  const activeCount = flocks.filter((f) => f.status === 'active').length
  const totalBirds = flocks.reduce((sum, f) => sum + (birdsByHouse[f.house.id] ?? f.initial_bird_count ?? 0), 0)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return flocks
    return flocks.filter((flock) => {
      const code = flockCodes[flock.id] || ''
      return (
        flock.house.name.toLowerCase().includes(q) ||
        (flock.breed || '').toLowerCase().includes(q) ||
        (flock.bird_type || '').toLowerCase().includes(q) ||
        code.toLowerCase().includes(q)
      )
    })
  }, [flocks, flockCodes, query])

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
            <Bird size={20} />
          </span>
          <div>
            <h1 className="font-display text-2xl font-extrabold text-navy">Flocks</h1>
            <p className="text-sm text-navy/60">Every active and past flock across your houses.</p>
          </div>
        </div>
        <div className="relative">
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-navy/40" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search flocks..."
            className="w-56 rounded-lg border border-hairline bg-surface py-2 pl-9 pr-3 text-sm outline-none focus:border-forest"
          />
        </div>
      </div>

      <div className="mt-6 grid grid-cols-3 gap-3">
        <StatCard label="Total Flocks" value={flocks.length} Icon={Bird} iconColor="#1B4332" />
        <StatCard label="Active" value={activeCount} caption={`of ${flocks.length}`} captionColor="#16222B" Icon={Building2} iconColor="#2F9E58" />
        <StatCard label="Total Birds" value={totalBirds.toLocaleString()} Icon={Weight} iconColor="#6C63D6" />
      </div>

      <div className="mt-6 overflow-hidden rounded-xl border border-hairline bg-surface shadow-sm">
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-navy/50">
            <Loader2 size={16} className="animate-spin" />
            Loading flocks...
          </div>
        ) : flocks.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-16 text-center">
            <Bird size={28} className="text-navy/20" />
            <p className="text-sm text-navy/50">No flocks yet.</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-16 text-center">
            <Search size={28} className="text-navy/20" />
            <p className="text-sm text-navy/50">No flocks match "{query}".</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead>
                <tr className="border-b border-hairline bg-bg text-xs uppercase tracking-wide text-navy/50">
                  <th className="py-3 px-4 font-semibold">Flock</th>
                  <th className="py-3 px-4 font-semibold">House</th>
                  <th className="py-3 px-4 font-semibold">Breed</th>
                  <th className="py-3 px-4 font-semibold">Age</th>
                  <th className="py-3 px-4 font-semibold">Birds</th>
                  <th className="py-3 px-4 font-semibold">Status</th>
                  <th className="py-3 px-4 font-semibold">Risk</th>
                  <th className="py-3 px-4" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((flock) => {
                  const risk = riskByHouse[flock.house.id]
                  const birds = birdsByHouse[flock.house.id] ?? flock.initial_bird_count
                  const typeColor = TYPE_COLOR[flock.bird_type] || '#16222B'
                  return (
                    <tr
                      key={flock.id}
                      onClick={() => navigate(`/houses/${flock.house.id}`)}
                      className="group cursor-pointer border-b border-hairline last:border-0 transition-colors hover:bg-forest/5"
                    >
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <span
                            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
                            style={{ backgroundColor: `${typeColor}14`, color: typeColor }}
                          >
                            <Bird size={15} />
                          </span>
                          <div>
                            <p className="font-semibold text-navy">Flock {flockCodes[flock.id]}</p>
                            <p className="text-xs capitalize text-navy/50">{flock.bird_type || 'Unspecified type'}</p>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-navy/70">
                        <span className="flex items-center gap-1.5">
                          <Building2 size={14} className="text-navy/40" />
                          {flock.house.name}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-navy/70">{flock.breed}</td>
                      <td className="py-3 px-4">
                        <span className="rounded-full bg-bg px-2 py-1 text-xs font-semibold text-navy/70">
                          {ageLabel(flock) || '—'}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-medium text-navy/70">{birds?.toLocaleString?.() ?? birds}</td>
                      <td className="py-3 px-4">
                        {risk?.risk_score != null ? (
                          <StatusBadge status={risk.risk_status} pill size="sm" />
                        ) : (
                          <span className="text-xs text-navy/40">No checks yet</span>
                        )}
                      </td>
                      <td
                        className="py-3 px-4 font-display font-bold"
                        style={{ color: risk?.risk_score != null ? statusMeta(risk.risk_status).color : undefined }}
                      >
                        {risk?.risk_score ?? '—'}
                      </td>
                      <td className="py-3 px-4">
                        <ChevronRight size={16} className="text-navy/25 transition-transform group-hover:translate-x-0.5" />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
