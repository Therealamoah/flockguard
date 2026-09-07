import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ChevronLeft,
  Warehouse,
  Users,
  Skull,
  Wheat,
  Droplets,
  Activity,
  Utensils,
  Stethoscope,
  StickyNote,
  Image as ImageIcon,
  Loader2,
} from 'lucide-react'
import { api } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import StatusBadge from '../components/StatusBadge'
import StatCard from '../components/StatCard'
import FactorBars from '../components/FactorBars'
import { statusMeta } from '../lib/risk'
import { formatClock } from '../lib/time'

export default function FlockCheckDetailPage() {
  const { houseId, checkId } = useParams()
  const { currentFarmId, houses } = useAppStore()
  const house = houses.find((h) => h.id === houseId)
  const [check, setCheck] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!currentFarmId || !houseId || !checkId) return
    let cancelled = false
    api.flockChecks
      .get(currentFarmId, houseId, checkId)
      .then((data) => {
        if (!cancelled) setCheck(data)
      })
      .catch(() => {
        if (!cancelled) setError('Could not load this Flock Check.')
      })
    return () => {
      cancelled = true
    }
  }, [currentFarmId, houseId, checkId])

  if (error) return <div className="p-6 text-sm text-critical">{error}</div>
  if (!check) {
    return (
      <div className="flex items-center justify-center gap-2 p-6 text-sm text-navy/50">
        <Loader2 size={16} className="animate-spin" />
        Loading Flock Check...
      </div>
    )
  }

  const meta = statusMeta(check.risk_status)
  const observations = [
    check.crowding_observed && 'Crowding observed',
    check.unusual_sound_observed && 'Unusual noise observed',
    check.sick_or_injured > 0 && `${check.sick_or_injured} sick/injured birds`,
  ].filter(Boolean)

  return (
    <div className="mx-auto max-w-2xl p-6">
      <Link to="/checks" className="flex items-center gap-1 text-xs font-semibold text-forest">
        <ChevronLeft size={14} />
        All Flock Checks
      </Link>

      <div className="mt-3 flex flex-wrap items-start justify-between gap-4 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
            <Warehouse size={20} />
          </span>
          <div>
            <h1 className="font-display text-2xl font-extrabold text-navy">{house?.name || houseId}</h1>
            <p className="mt-1 text-sm capitalize text-navy/60">
              {check.period} check · {formatClock(check.recorded_at)}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div
            className="relative flex h-16 w-16 shrink-0 items-center justify-center rounded-full"
            style={{ background: `conic-gradient(${meta.color} ${check.risk_score * 3.6}deg, #E4E1D8 0deg)` }}
          >
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-surface">
              <span className="font-display text-lg font-extrabold" style={{ color: meta.color }}>
                {check.risk_score}
              </span>
            </div>
          </div>
          <div>
            <p className="text-xs text-navy/40">Risk score / 100</p>
            <StatusBadge status={check.risk_status} size="sm" />
          </div>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Bird Count" value={check.bird_count ?? '—'} Icon={Users} iconColor="#1B4332" />
        <StatCard label="Mortality" value={check.mortality ?? '—'} Icon={Skull} iconColor="#C8433A" />
        <StatCard label="Feed (kg)" value={check.feed_kg ?? '—'} Icon={Wheat} iconColor="#C05A1D" />
        <StatCard
          label="Water"
          value={check.water_liters ? `${check.water_liters}L` : check.water_level ?? '—'}
          Icon={Droplets}
          iconColor="#6C63D6"
        />
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-hairline bg-surface p-4 shadow-sm">
          <p className="flex items-center gap-1.5 text-xs text-navy/40">
            <Activity size={13} />
            Activity
          </p>
          <p className="mt-1 text-sm font-semibold capitalize text-navy">{check.activity}</p>
        </div>
        <div className="rounded-xl border border-hairline bg-surface p-4 shadow-sm">
          <p className="flex items-center gap-1.5 text-xs text-navy/40">
            <Utensils size={13} />
            Feeding behaviour
          </p>
          <p className="mt-1 text-sm font-semibold capitalize text-navy">{check.feeding_behaviour}</p>
        </div>
        {observations.length > 0 ? (
          <div className="rounded-xl border border-hairline bg-surface p-4 shadow-sm sm:col-span-2">
            <p className="text-xs text-navy/40">Other observations</p>
            <p className="mt-1 text-sm text-navy">{observations.join(' · ')}</p>
          </div>
        ) : null}
      </div>

      <div className="mt-4 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
        <div className="flex items-center gap-2">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-forest/10 text-forest">
            <Stethoscope size={14} />
          </span>
          <h2 className="text-sm font-bold text-navy">
            {check.risk_factors?.length > 0 ? 'Why this check was flagged' : 'Risk factor breakdown'}
          </h2>
        </div>
        <div className="mt-4">
          <FactorBars factors={check.risk_factors} />
        </div>
      </div>

      {check.notes ? (
        <div className="mt-4 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-forest/10 text-forest">
              <StickyNote size={14} />
            </span>
            <h2 className="text-sm font-bold text-navy">Notes</h2>
          </div>
          <p className="mt-3 text-sm text-navy/70">{check.notes}</p>
        </div>
      ) : null}

      {check.photo_url || check.audio_url ? (
        <div className="mt-4 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-forest/10 text-forest">
              <ImageIcon size={14} />
            </span>
            <h2 className="text-sm font-bold text-navy">Media</h2>
          </div>
          <div className="mt-4 space-y-3">
            {check.photo_url ? (
              <img src={check.photo_url} alt="Flock check" className="max-h-64 rounded-lg border border-hairline" />
            ) : null}
            {check.audio_url ? <audio controls src={check.audio_url} className="w-full" /> : null}
          </div>
        </div>
      ) : null}

      <div className="mt-6">
        <Link
          to={`/houses/${houseId}`}
          className="rounded-lg border border-hairline px-5 py-2.5 text-sm font-bold text-navy hover:bg-forest/5"
        >
          View House
        </Link>
      </div>
    </div>
  )
}
