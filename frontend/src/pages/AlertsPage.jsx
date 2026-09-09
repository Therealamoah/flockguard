import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldAlert, Building2, MessageCircle, Check, Loader2, ShieldCheck, Stethoscope } from 'lucide-react'
import { api } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import StatusBadge from '../components/StatusBadge'
import FactorBars from '../components/FactorBars'
import { timeAgo } from '../lib/time'

const FILTERS = ['open', 'resolved', 'all']

export default function AlertsPage() {
  const { houses } = useAppStore()
  const navigate = useNavigate()
  const [alerts, setAlerts] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [filter, setFilter] = useState('open')

  async function load() {
    setIsLoading(true)
    const data = await api.alerts.list({ resolved: filter === 'open' ? false : filter === 'resolved' ? true : undefined })
    setAlerts(data)
    setIsLoading(false)
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter])

  async function handleAcknowledge(id) {
    await api.alerts.acknowledge(id)
    setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, acknowledged: true } : a)))
  }

  async function handleResolve(id) {
    await api.alerts.resolve(id)
    if (filter === 'open') {
      setAlerts((prev) => prev.filter((a) => a.id !== id))
    } else {
      setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, resolved: true } : a)))
    }
  }

  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-critical/10 text-critical">
            <ShieldAlert size={20} />
          </span>
          <div>
            <h1 className="font-display text-2xl font-extrabold text-navy">Alerts</h1>
            <p className="text-sm text-navy/60">Issues the Risk Engine flagged for your attention.</p>
          </div>
        </div>
        <div className="flex gap-1 rounded-lg border border-hairline bg-surface p-1">
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={[
                'rounded-md px-3 py-1.5 text-xs font-semibold capitalize transition-colors',
                filter === f ? 'bg-forest text-white' : 'text-navy/60 hover:bg-forest/5',
              ].join(' ')}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-6 space-y-4">
        {isLoading ? (
          <div className="flex items-center justify-center gap-2 rounded-xl border border-hairline bg-surface py-16 text-sm text-navy/50 shadow-sm">
            <Loader2 size={16} className="animate-spin" />
            Loading alerts...
          </div>
        ) : alerts.length === 0 ? (
          <div className="flex flex-col items-center gap-2 rounded-xl border border-hairline bg-surface py-16 text-center shadow-sm">
            <ShieldCheck size={28} className="text-navy/20" />
            <p className="text-sm text-navy/50">No {filter !== 'all' ? filter : ''} alerts.</p>
          </div>
        ) : (
          alerts.map((alert) => {
            const house = houses.find((h) => h.id === alert.house_id)
            return (
              <div key={alert.id} className="rounded-xl border border-hairline bg-surface p-5 shadow-sm">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-critical/10 text-critical">
                      <Building2 size={16} />
                    </span>
                    <div>
                      <p className="font-display text-base font-bold text-navy">{house?.name || alert.house_id}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <StatusBadge status={alert.status} score={alert.score} />
                        {alert.previous_risk_score != null ? (
                          <span className="text-xs font-semibold text-navy/50">
                            {alert.previous_risk_score} → {alert.score}
                            {alert.risk_change != null ? ` (${alert.risk_change > 0 ? '+' : ''}${alert.risk_change})` : ''}
                          </span>
                        ) : null}
                        {alert.occurrence_count > 1 ? (
                          <span className="rounded-full bg-hairline/70 px-2 py-0.5 text-xs font-semibold text-navy/60">
                            Seen {alert.occurrence_count}×
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-navy/40">{timeAgo(alert.created_at)}</p>
                    {alert.resolved ? (
                      <span className="mt-2 flex items-center gap-1 text-xs font-semibold text-normal">
                        <Check size={12} />
                        Resolved
                      </span>
                    ) : alert.acknowledged ? (
                      <span className="mt-2 flex items-center gap-1 text-xs font-semibold text-navy/50">
                        <Check size={12} />
                        Seen
                      </span>
                    ) : null}
                  </div>
                </div>

                <div className="mt-4 border-t border-hairline pt-4">
                  <p className="text-xs font-bold uppercase tracking-wide text-navy/40">Why this house is flagged</p>
                  <div className="mt-3">
                    <FactorBars factors={alert.factors} />
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2 border-t border-hairline pt-4">
                  <button
                    onClick={() => navigate(`/houses/${alert.house_id}`)}
                    className="flex items-center gap-1.5 rounded-lg border border-hairline px-3 py-1.5 text-xs font-semibold text-navy hover:bg-forest/5"
                  >
                    <Building2 size={13} />
                    View House
                  </button>
                  <button
                    onClick={() => navigate('/ask')}
                    className="flex items-center gap-1.5 rounded-lg border border-hairline px-3 py-1.5 text-xs font-semibold text-navy hover:bg-forest/5"
                  >
                    <MessageCircle size={13} />
                    Ask FlockGuard
                  </button>
                  {!alert.acknowledged ? (
                    <button
                      onClick={() => handleAcknowledge(alert.id)}
                      className="flex items-center gap-1.5 rounded-lg border border-hairline px-3 py-1.5 text-xs font-semibold text-navy hover:bg-forest/5"
                    >
                      <Check size={13} />
                      Acknowledge
                    </button>
                  ) : null}
                  {!alert.resolved ? (
                    <button
                      onClick={() => handleResolve(alert.id)}
                      className="flex items-center gap-1.5 rounded-lg bg-forest px-3 py-1.5 text-xs font-semibold text-white hover:bg-forest-dark"
                    >
                      <Stethoscope size={13} />
                      Resolve
                    </button>
                  ) : null}
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
