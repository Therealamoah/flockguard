import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ClipboardList, Plus, Building2, Sun, Moon, Siren, Clock3, ChevronRight, Loader2, Inbox } from 'lucide-react'
import { api } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import StatusBadge from '../components/StatusBadge'
import { timeAgo } from '../lib/time'

const PERIOD_ICON = { morning: Sun, evening: Moon, emergency: Siren }

export default function FlockChecksListPage() {
  const { currentFarmId, houses } = useAppStore()
  const navigate = useNavigate()
  const [checks, setChecks] = useState([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!currentFarmId || houses.length === 0) {
      setIsLoading(false)
      return
    }
    let cancelled = false
    Promise.all(
      houses.map((h) =>
        api.flockChecks.list(currentFarmId, h.id).then((list) => list.map((c) => ({ ...c, house: h })))
      )
    ).then((results) => {
      if (cancelled) return
      const merged = results.flat().sort((a, b) => new Date(b.recorded_at) - new Date(a.recorded_at))
      setChecks(merged)
      setIsLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [currentFarmId, houses])

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
            <ClipboardList size={20} />
          </span>
          <div>
            <h1 className="font-display text-2xl font-extrabold text-navy">Flock Checks</h1>
            <p className="text-sm text-navy/60">Every recorded check across your farm.</p>
          </div>
        </div>
        <Link
          to="/checks/new"
          className="flex items-center gap-1.5 rounded-lg bg-forest px-4 py-2.5 text-sm font-bold text-white hover:bg-forest-dark"
        >
          <Plus size={16} />
          New Check
        </Link>
      </div>

      <div className="mt-6 overflow-hidden rounded-xl border border-hairline bg-surface shadow-sm">
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-navy/50">
            <Loader2 size={16} className="animate-spin" />
            Loading checks...
          </div>
        ) : checks.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-16 text-center">
            <Inbox size={28} className="text-navy/20" />
            <p className="text-sm text-navy/50">No Flock Checks recorded yet.</p>
          </div>
        ) : (
          <div className="divide-y divide-hairline">
            {checks.map((c) => {
              const PeriodIcon = PERIOD_ICON[c.period] || Clock3
              return (
                <div
                  key={c.id}
                  onClick={() => navigate(`/houses/${c.house.id}/checks/${c.id}`)}
                  className="group flex cursor-pointer items-center gap-3 px-4 py-3 text-sm transition-colors hover:bg-forest/5"
                >
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-bg text-navy/50">
                    <PeriodIcon size={15} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-1.5 font-semibold text-navy">
                      <Building2 size={13} className="shrink-0 text-navy/40" />
                      {c.house.name}
                    </p>
                    <p className="text-xs capitalize text-navy/50">
                      {c.period} · {timeAgo(c.recorded_at)}
                    </p>
                  </div>
                  <span className="hidden text-navy/60 sm:block">Mortality {c.mortality}</span>
                  <StatusBadge status={c.risk_status} score={c.risk_score} size="sm" />
                  <ChevronRight size={16} className="shrink-0 text-navy/25 transition-transform group-hover:translate-x-0.5" />
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
