import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import { useAuthStore } from '../store/useAuthStore'
import RadarCanvas from '../components/RadarCanvas'
import StatCard from '../components/StatCard'
import { statusMeta } from '../lib/risk'
import { greetingFor, formatDateLong, formatTime, timeAgo, formatClock } from '../lib/time'
import { displayName } from '../lib/format'
import { ShieldCheck, Bird, Warehouse, Bell, ClipboardList, Sun, Moon, Loader2, Sparkles, X } from 'lucide-react'

const PRIORITY_COLOR = { low: '#2F9E58', medium: '#B3811A', high: '#C05A1D', urgent: '#C8433A' }

function useClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 30000)
    return () => clearInterval(id)
  }, [])
  return now
}

export default function OverviewPage() {
  const { currentFarmId, houses } = useAppStore()
  const { user } = useAuthStore()
  const now = useClock()
  const [compare, setCompare] = useState([])
  const [alerts, setAlerts] = useState([])
  const [activity, setActivity] = useState([])
  const [totalBirds, setTotalBirds] = useState(null)
  const [activeFlocks, setActiveFlocks] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [brief, setBrief] = useState(null)
  const [recommendations, setRecommendations] = useState([])

  useEffect(() => {
    if (!currentFarmId) return
    let cancelled = false

    async function load() {
      setIsLoading(true)
      const [compareData, alertsData, checksByHouse, flocksByHouse] = await Promise.all([
        api.analytics.compareHouses(currentFarmId),
        api.alerts.list({ resolved: false }),
        Promise.all(
          houses.map((h) =>
            api.flockChecks
              .list(currentFarmId, h.id)
              .then((checks) => ({ house: h, checks }))
              .catch(() => ({ house: h, checks: [] }))
          )
        ),
        Promise.all(
          houses.map((h) =>
            api.flocks
              .list(currentFarmId, h.id)
              .then((flocks) => ({ house: h, flocks }))
              .catch(() => ({ house: h, flocks: [] }))
          )
        ),
      ])
      if (cancelled) return

      let birdTotal = 0
      let hasBirdData = false
      let activeFlockCount = 0
      for (const { house, flocks } of flocksByHouse) {
        const activeFlock = flocks.find((f) => f.status === 'active')
        activeFlockCount += flocks.filter((f) => f.status === 'active').length
        const latestCheck = checksByHouse.find((c) => c.house.id === house.id)?.checks[0]
        const birds = latestCheck?.bird_count ?? activeFlock?.initial_bird_count ?? null
        if (birds != null) {
          birdTotal += birds
          hasBirdData = true
        }
      }
      setTotalBirds(hasBirdData ? birdTotal : null)
      setActiveFlocks(activeFlockCount)

      const events = []
      for (const { house, checks } of checksByHouse) {
        if (checks[0]) {
          events.push({
            key: `check-${checks[0].id}`,
            at: checks[0].recorded_at,
            color: statusMeta(checks[0].risk_status).color,
            text: `Check done in ${house.name}`,
          })
          if (checks[1] && checks[1].risk_score !== checks[0].risk_score) {
            events.push({
              key: `delta-${checks[0].id}`,
              at: checks[0].recorded_at,
              color: statusMeta(checks[0].risk_status).color,
              text: `${house.name}: risk went from ${checks[1].risk_score} to ${checks[0].risk_score}`,
            })
          }
        }
      }
      for (const alert of alertsData) {
        const house = houses.find((h) => h.id === alert.house_id)
        events.push({
          key: `alert-${alert.id}`,
          at: alert.created_at,
          color: statusMeta(alert.status).color,
          text: `New ${statusMeta(alert.status).label.toLowerCase()} warning for ${house?.name || alert.house_id}`,
        })
      }
      events.sort((a, b) => new Date(b.at) - new Date(a.at))

      setCompare(compareData)
      setAlerts(alertsData)
      setActivity(events.slice(0, 8))
      setIsLoading(false)
    }

    load()
    return () => {
      cancelled = true
    }
  }, [currentFarmId, houses])

  useEffect(() => {
    if (!currentFarmId) return
    let cancelled = false
    // Deterministic first, AI-reworded on top - never blocks or breaks the
    // dashboard if Grok is unavailable (see backend app/api/routes/ask.py::ai_daily_brief).
    api.askDailyBrief(currentFarmId)
      .then((data) => {
        if (!cancelled) setBrief(data)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [currentFarmId])

  useEffect(() => {
    if (!currentFarmId) return
    let cancelled = false
    // FlockGuard Agent recommendations from event-triggered investigations
    // (backend/app/agent/) - real, persisted, tenant-scoped; empty array if
    // nothing is open, never fabricated.
    api.agent
      .recommendations({ farmId: currentFarmId, status: 'open' })
      .then((data) => {
        if (!cancelled) setRecommendations(data)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [currentFarmId])

  async function handleDismissRecommendation(id) {
    setRecommendations((prev) => prev.filter((r) => r.id !== id))
    try {
      await api.agent.dismiss(id)
    } catch {
      // best-effort - already removed from view; a stale server-side "open"
      // status isn't worth surfacing an error to the farmer over.
    }
  }

  const checkedHouses = compare.filter((h) => h.risk_score !== null)
  const farmHealth = checkedHouses.length
    ? Math.round(100 - checkedHouses.reduce((sum, h) => sum + h.risk_score, 0) / checkedHouses.length)
    : null
  const worst = compare[0]
  const lastCheckedHouse = compare
    .filter((h) => h.last_checked_at)
    .sort((a, b) => new Date(b.last_checked_at) - new Date(a.last_checked_at))[0]
  const criticalCount = alerts.filter((a) => a.status === 'critical').length
  const firstName = displayName(user).split(' ')[0]
  const hour = now.getHours()
  const isDaytime = hour >= 6 && hour < 18
  const TimeIcon = isDaytime ? Sun : Moon

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 p-6 text-sm text-secondary">
        <Loader2 size={16} className="animate-spin" />
        Getting your farm ready...
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="overflow-hidden rounded-xl bg-linear-to-br from-forest to-forest-dark p-6 text-white shadow-sm sm:p-8">
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-center">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-white/50">{formatDateLong(now)}</p>
            <h1 className="mt-1 font-display text-2xl font-extrabold capitalize sm:text-3xl">
              {greetingFor(now)}, {firstName}
            </h1>
            <p className="mt-2 text-sm text-white/80">Here's how your farm is doing today.</p>
          </div>
          <div className="flex items-center gap-3 self-start rounded-lg bg-white/10 px-4 py-3 sm:self-auto">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/15 text-white">
              <TimeIcon size={18} />
            </span>
            <span className="font-display text-xl font-extrabold tabular-nums leading-none sm:text-2xl">
              {formatTime(now)}
            </span>
          </div>
        </div>
      </div>

      {brief?.available ? (
        <div className="mt-6 rounded-xl border border-ai/20 bg-ai/5 p-5">
          <div className="flex items-center gap-2 text-sm font-bold text-navy">
            <Sparkles size={14} className="text-ai" />
            Today's update
          </div>
          <p className="mt-2 text-sm text-secondary">{brief.ai_text || brief.brief_text}</p>
        </div>
      ) : null}

      {recommendations.length > 0 ? (
        <div className="mt-6 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
          <div className="flex items-center gap-2 text-sm font-bold text-navy">
            <Sparkles size={14} className="text-ai" />
            FlockGuard suggests — {recommendations.length} thing{recommendations.length === 1 ? '' : 's'} to do
          </div>
          <div className="mt-3 space-y-2">
            {recommendations.map((rec) => {
              const house = houses.find((h) => h.id === rec.house_id)
              const color = PRIORITY_COLOR[rec.priority] || PRIORITY_COLOR.medium
              return (
                <div key={rec.id} className="flex items-start gap-3 rounded-lg border border-hairline p-3">
                  <span
                    className="mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-xs font-bold uppercase"
                    style={{ color, backgroundColor: `${color}1A` }}
                  >
                    {rec.priority}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-navy">
                      {house?.name || 'Farm'}: {rec.title}
                    </p>
                    {rec.recommended_actions?.[0] ? (
                      <p className="mt-0.5 text-xs text-secondary">{rec.recommended_actions[0]}</p>
                    ) : null}
                    {house ? (
                      <Link to={`/houses/${house.id}`} className="mt-1 inline-block text-xs font-semibold text-forest">
                        View house →
                      </Link>
                    ) : null}
                  </div>
                  <button
                    onClick={() => handleDismissRecommendation(rec.id)}
                    className="shrink-0 rounded p-1 text-muted hover:bg-hairline/50 hover:text-navy"
                    title="Dismiss"
                  >
                    <X size={14} />
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      ) : null}

      <div className="mt-6 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
        {worst && worst.risk_score !== null ? (
          <>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-secondary">
                  Check this house first
                </p>
                <p className="mt-1 font-display text-lg font-bold text-navy">
                  {worst.house_name} — {statusMeta(worst.risk_status).label}, risk {worst.risk_score}
                </p>
              </div>
              <Link to="/radar" className="text-sm font-semibold text-forest">
                See all houses →
              </Link>
            </div>
            <div className="mt-4 flex justify-center">
              <RadarCanvas houses={compare} size={200} />
            </div>
            {worst.risk_status !== 'normal' ? (
              <p className="text-center text-sm text-secondary">
                Go and check {worst.house_name} first
              </p>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-secondary">
            No checks done yet.{' '}
            <Link to="/checks/new" className="font-semibold text-forest">
              Do your first check
            </Link>
            .
          </p>
        )}
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <StatCard
          label="Farm health"
          value={farmHealth !== null ? `${farmHealth}%` : '—'}
          caption={farmHealth !== null ? 'Doing fine' : null}
          captionColor="#2F9E58"
          Icon={ShieldCheck}
          iconColor="#2F9E58"
        />
        <StatCard
          label="All birds"
          value={totalBirds !== null ? totalBirds.toLocaleString() : '—'}
          caption={`In ${houses.length} house${houses.length === 1 ? '' : 's'}`}
          captionColor="#16222B"
          Icon={Bird}
          iconColor="#1B4332"
        />
        <StatCard label="Flocks now" value={activeFlocks} captionColor="#16222B" Icon={Warehouse} iconColor="#1B4332" />
        <StatCard
          label="Warnings"
          value={alerts.length}
          caption={criticalCount ? `${criticalCount} serious` : null}
          captionColor="#C8433A"
          Icon={Bell}
          iconColor="#C8433A"
        />
        <StatCard
          label="Last check"
          value={lastCheckedHouse ? timeAgo(lastCheckedHouse.last_checked_at) : '—'}
          caption={lastCheckedHouse?.house_name}
          captionColor="#16222B"
          Icon={ClipboardList}
          iconColor="#1B4332"
        />
      </div>

      <div className="mt-6 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-bold text-navy">What happened today</h2>
          <Link to="/checks" className="text-xs font-semibold text-forest">
            View all
          </Link>
        </div>
        <div className="mt-3 space-y-2">
          {activity.length === 0 ? (
            <p className="text-sm text-secondary">Nothing recorded yet today.</p>
          ) : (
            activity.map((event) => (
              <div key={event.key} className="flex items-start gap-3 border-l-2 pl-3" style={{ borderColor: event.color }}>
                <span className="w-14 shrink-0 text-xs text-muted">{formatClock(event.at)}</span>
                <span className="text-sm text-navy">{event.text}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
