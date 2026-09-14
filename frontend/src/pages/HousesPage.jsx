import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Warehouse, Plus, Users, ChevronRight } from 'lucide-react'
import { api } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import StatusBadge from '../components/StatusBadge'

export default function HousesPage() {
  const { currentFarmId, houses, refreshHouses } = useAppStore()
  const [risk, setRisk] = useState({})
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [capacity, setCapacity] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [createError, setCreateError] = useState('')

  useEffect(() => {
    if (!currentFarmId) return
    api.analytics.compareHouses(currentFarmId).then((data) => {
      const map = {}
      for (const h of data) map[h.house_id] = h
      setRisk(map)
    })
  }, [currentFarmId, houses])

  async function handleCreate(e) {
    e.preventDefault()
    setCreateError('')
    setIsSubmitting(true)
    try {
      await api.houses.create(currentFarmId, { name, bird_capacity: capacity ? Number(capacity) : null })
      setName('')
      setCapacity('')
      setShowForm(false)
      await refreshHouses()
    } catch (err) {
      setCreateError(err.detail || 'Could not add this house.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
            <Warehouse size={20} />
          </span>
          <div>
            <h1 className="font-display text-2xl font-extrabold text-navy">Houses</h1>
            <p className="text-sm text-secondary">Every poultry house on your farm.</p>
          </div>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-1.5 rounded-lg bg-forest px-4 py-2.5 text-sm font-bold text-white hover:bg-forest-dark"
        >
          <Plus size={16} />
          Add House
        </button>
      </div>

      {showForm ? (
        <form
          onSubmit={handleCreate}
          className="mt-4 flex flex-wrap items-end gap-3 rounded-xl border border-hairline bg-surface p-4 shadow-sm"
        >
          <div>
            <label className="mb-1 block text-xs font-semibold text-navy">Name</label>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-semibold text-navy">Capacity</label>
            <input
              type="number"
              value={capacity}
              onChange={(e) => setCapacity(e.target.value)}
              className="rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest"
            />
          </div>
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-lg bg-forest px-4 py-2 text-sm font-bold text-white hover:bg-forest-dark disabled:opacity-60"
          >
            {isSubmitting ? 'Adding...' : 'Save'}
          </button>
          {createError ? <p className="w-full text-sm text-critical">{createError}</p> : null}
        </form>
      ) : null}

      {houses.length === 0 ? (
        <div className="mt-6 flex flex-col items-center gap-2 rounded-xl border border-hairline bg-surface py-16 text-center shadow-sm">
          <Warehouse size={28} className="text-muted" />
          <p className="text-sm text-secondary">No houses yet. Add your first one to get started.</p>
        </div>
      ) : (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {houses.map((house) => {
            const r = risk[house.id]
            return (
              <Link
                key={house.id}
                to={`/houses/${house.id}`}
                className="group rounded-xl border border-hairline bg-surface p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:border-forest hover:shadow-md"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
                      <Warehouse size={18} />
                    </span>
                    <div>
                      <p className="font-display text-base font-bold text-navy">{house.name}</p>
                      {house.bird_capacity ? (
                        <p className="mt-0.5 flex items-center gap-1 text-xs text-secondary">
                          <Users size={11} />
                          Capacity {house.bird_capacity.toLocaleString()} birds
                        </p>
                      ) : null}
                    </div>
                  </div>
                  <ChevronRight size={16} className="mt-2 shrink-0 text-muted transition-transform group-hover:translate-x-0.5" />
                </div>
                <div className="mt-4 border-t border-hairline pt-3">
                  {r?.risk_score != null ? (
                    <StatusBadge status={r.risk_status} score={r.risk_score} size="sm" />
                  ) : (
                    <span className="text-xs text-muted">No checks yet</span>
                  )}
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
