import { useEffect, useState } from 'react'
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom'
import {
  ChevronLeft,
  ChevronRight,
  Warehouse,
  ClipboardList,
  Users,
  Clock3,
  Activity,
  TrendingUp,
  TrendingDown,
  Minus,
  Stethoscope,
  ClipboardCheck,
  MessageCircle,
  Skull,
  Wheat,
  Droplets,
  LineChart,
  Sun,
  Moon,
  Siren,
  Loader2,
  Sparkles,
  TrendingUp as TrendUpIcon,
} from 'lucide-react'
import { api } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import StatusBadge from '../components/StatusBadge'
import StatCard from '../components/StatCard'
import TrendCard from '../components/TrendCard'
import FactorBars from '../components/FactorBars'
import { statusMeta } from '../lib/risk'
import { formatClock, timeAgo } from '../lib/time'
import { dayLabel } from '../lib/format'

const PERIOD_ICON = { morning: Sun, evening: Moon, emergency: Siren }

const FINDING_CATEGORIES = [
  { value: 'everything_normal', label: 'Everything normal' },
  { value: 'water_issue', label: 'Water problem' },
  { value: 'feed_issue', label: 'Feed problem' },
  { value: 'ventilation_issue', label: 'Ventilation problem' },
  { value: 'sick_birds_observed', label: 'Sick birds observed' },
  { value: 'behaviour_issue', label: 'Behaviour problem' },
  { value: 'other', label: 'Other' },
]

export default function HouseDetailPage() {
  const { houseId } = useParams()
  const { currentFarmId, houses } = useAppStore()
  const house = houses.find((h) => h.id === houseId)
  const navigate = useNavigate()
  const location = useLocation()

  const [trends, setTrends] = useState([])
  const [checks, setChecks] = useState([])
  const [flock, setFlock] = useState(null)
  const [openAlert, setOpenAlert] = useState(null)
  const [insights, setInsights] = useState([])
  const [inspections, setInspections] = useState([])
  const [isLoading, setIsLoading] = useState(true)

  const [showInspection, setShowInspection] = useState(Boolean(location.state?.openInspection))
  const [findings, setFindings] = useState('')
  const [findingCategory, setFindingCategory] = useState('')
  const [actionTaken, setActionTaken] = useState('')
  const [isSubmittingInspection, setIsSubmittingInspection] = useState(false)
  const [inspectionDone, setInspectionDone] = useState(false)

  const [explanation, setExplanation] = useState('')
  const [explanationLoading, setExplanationLoading] = useState(false)

  useEffect(() => {
    if (!currentFarmId || !houseId) return
    let cancelled = false
    Promise.all([
      api.analytics.houseTrends(currentFarmId, houseId),
      api.flockChecks.list(currentFarmId, houseId),
      api.flocks.list(currentFarmId, houseId),
      api.alerts.list({ resolved: false }),
      api.analytics.trendInsights(currentFarmId).catch(() => []),
      api.inspections.list(currentFarmId, houseId).catch(() => []),
    ]).then(([trendData, checkData, flockData, alertData, insightData, inspectionData]) => {
      if (cancelled) return
      setTrends(trendData)
      setChecks(checkData)
      setFlock(flockData.find((f) => f.status === 'active') || flockData[0] || null)
      setOpenAlert(alertData.find((a) => a.house_id === houseId) || null)
      setInsights((insightData || []).filter((i) => i.house_id === houseId))
      setInspections(inspectionData || [])
      setExplanation('')
      setIsLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [currentFarmId, houseId])

  const latest = checks[0]
  // Prefer the value the backend persisted at submission time; fall back to
  // comparing against the previous check client-side for older records that
  // predate that field.
  const previousScore = latest?.previous_risk_score ?? checks[1]?.risk_score

  function handlePerformCheck() {
    useAppStore.getState().selectHouse(houseId)
    navigate('/checks/new')
  }

  async function handleSubmitInspection(e) {
    e.preventDefault()
    setIsSubmittingInspection(true)
    try {
      const created = await api.inspections.create(currentFarmId, houseId, {
        findings,
        finding_category: findingCategory || null,
        action_taken: actionTaken || null,
        alert_id: openAlert?.id ?? null,
      })
      setInspectionDone(true)
      setShowInspection(false)
      setOpenAlert(null)
      setInspections((prev) => [created, ...prev])
    } finally {
      setIsSubmittingInspection(false)
    }
  }

  async function handleExplain() {
    if (!latest) return
    setExplanationLoading(true)
    try {
      const { available, explanation: text } = await api.askExplain(currentFarmId, houseId, latest.id)
      setExplanation(
        available
          ? text
          : "FlockGuard AI explanations are temporarily unavailable. Your farm monitoring and risk calculations are still working."
      )
    } catch {
      setExplanation(
        "FlockGuard AI explanations are temporarily unavailable. Your farm monitoring and risk calculations are still working."
      )
    } finally {
      setExplanationLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 p-6 text-sm text-navy/50">
        <Loader2 size={16} className="animate-spin" />
        Loading house data...
      </div>
    )
  }

  const riskDelta = latest && previousScore != null ? latest.risk_score - previousScore : null
  const RiskTrendIcon = riskDelta == null || riskDelta === 0 ? Minus : riskDelta > 0 ? TrendingUp : TrendingDown
  const riskTrendColor = riskDelta == null || riskDelta === 0 ? '#16222B' : riskDelta > 0 ? '#C8433A' : '#2F9E58'

  return (
    <div className="mx-auto max-w-6xl p-6">
      <Link to="/houses" className="flex items-center gap-1 text-xs font-semibold text-forest">
        <ChevronLeft size={14} />
        All houses
      </Link>

      <div className="mt-3 flex flex-wrap items-start justify-between gap-4 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
            <Warehouse size={20} />
          </span>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="font-display text-2xl font-extrabold text-navy">{house?.name || houseId}</h1>
              {latest ? <StatusBadge status={latest.risk_status} /> : null}
            </div>
            <p className="mt-1 text-sm capitalize text-navy/60">
              {flock ? `${flock.bird_type || ''} Flock · ${flock.breed}`.trim() : 'No active flock'}
            </p>
          </div>
        </div>

        {latest ? (
          <div className="flex items-center gap-3">
            <div
              className="relative flex h-16 w-16 shrink-0 items-center justify-center rounded-full"
              style={{
                background: `conic-gradient(${statusMeta(latest.risk_status).color} ${latest.risk_score * 3.6}deg, #E4E1D8 0deg)`,
              }}
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-surface">
                <span className="font-display text-lg font-extrabold" style={{ color: statusMeta(latest.risk_status).color }}>
                  {latest.risk_score}
                </span>
              </div>
            </div>
            <div>
              <p className="text-xs text-navy/40">Risk score / 100</p>
              {riskDelta != null ? (
                <span className="flex items-center gap-1 text-xs font-semibold" style={{ color: riskTrendColor }}>
                  <RiskTrendIcon size={12} />
                  {Math.abs(riskDelta)} vs previous
                </span>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-5">
        <StatCard label="Current Flock" value={flock ? flock.breed : '—'} Icon={ClipboardList} iconColor="#1B4332" />
        <StatCard
          label="Bird Count"
          value={latest?.bird_count ?? flock?.initial_bird_count ?? '—'}
          Icon={Users}
          iconColor="#1B4332"
        />
        <StatCard label="Bird Age" value={flock ? dayLabel(flock.start_date) : '—'} Icon={Clock3} iconColor="#1B4332" />
        <StatCard label="Last Check" value={latest ? timeAgo(latest.recorded_at) : '—'} Icon={Activity} iconColor="#1B4332" />
        <StatCard
          label="Previous Risk"
          value={previousScore ?? '—'}
          caption={riskDelta != null ? (riskDelta > 0 ? 'Worsening' : riskDelta < 0 ? 'Improving' : 'Unchanged') : null}
          captionColor={riskTrendColor}
          Icon={RiskTrendIcon}
          iconColor={riskTrendColor}
        />
      </div>

      {insights.length > 0 ? (
        <div className="mt-6 rounded-xl border border-watch/30 bg-watch/5 p-4">
          <div className="flex items-center gap-2 text-sm font-bold text-navy">
            <TrendUpIcon size={15} className="text-watch" />
            Proactive insight
          </div>
          <ul className="mt-2 space-y-1 text-sm text-navy/70">
            {insights.map((insight) => (
              <li key={insight.type}>{insight.message}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {!latest ? (
        <p className="mt-6 text-sm text-navy/50">
          No Flock Checks recorded yet.{' '}
          <button onClick={handlePerformCheck} className="font-semibold text-forest">
            Record the first one
          </button>
          .
        </p>
      ) : (
        <>
          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-hairline bg-surface p-5 shadow-sm">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-forest/10 text-forest">
                    <Stethoscope size={14} />
                  </span>
                  <h2 className="text-sm font-bold text-navy">
                    {latest.risk_factors.length > 0 ? 'Why this house is flagged' : 'Latest check summary'}
                  </h2>
                </div>
                {latest.risk_status !== 'normal' ? (
                  <button
                    onClick={handleExplain}
                    disabled={explanationLoading}
                    className="flex shrink-0 items-center gap-1 rounded-full border border-ai/30 px-2.5 py-1 text-xs font-semibold text-ai hover:bg-ai/10 disabled:opacity-60"
                  >
                    <Sparkles size={12} />
                    {explanationLoading ? 'Asking...' : 'Why?'}
                  </button>
                ) : null}
              </div>
              <div className="mt-4">
                <FactorBars factors={latest.risk_factors} />
              </div>
              {explanation ? (
                <p className="mt-4 border-t border-hairline pt-4 text-sm text-navy/70">{explanation}</p>
              ) : null}
            </div>

            <div className="rounded-xl border border-hairline bg-surface p-5 shadow-sm">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-forest/10 text-forest">
                  <ClipboardCheck size={14} />
                </span>
                <h2 className="text-sm font-bold text-navy">Recommended actions</h2>
              </div>
              <div className="mt-4 space-y-2">
                <button
                  onClick={handlePerformCheck}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-forest py-2.5 text-sm font-bold text-white hover:bg-forest-dark"
                >
                  <ClipboardList size={15} />
                  Perform Flock Check
                </button>
                <button
                  onClick={() => navigate('/ask')}
                  className="flex w-full items-center justify-center gap-2 rounded-lg border border-hairline py-2.5 text-sm font-bold text-navy hover:bg-forest/5"
                >
                  <MessageCircle size={15} />
                  Ask FlockGuard
                </button>
                <button
                  onClick={() => setShowInspection((v) => !v)}
                  className="flex w-full items-center justify-center gap-2 rounded-lg border border-hairline py-2.5 text-sm font-bold text-navy hover:bg-forest/5"
                >
                  <Stethoscope size={15} />
                  Record Inspection
                </button>
              </div>

              {inspectionDone ? (
                <p className="mt-3 text-sm text-normal">Inspection recorded ✓</p>
              ) : null}

              {showInspection ? (
                <form onSubmit={handleSubmitInspection} className="mt-3 space-y-2 border-t border-hairline pt-3">
                  <p className="text-xs font-semibold text-navy/50">What did you find?</p>
                  <div className="flex flex-wrap gap-1.5">
                    {FINDING_CATEGORIES.map((cat) => (
                      <button
                        key={cat.value}
                        type="button"
                        onClick={() => setFindingCategory(cat.value)}
                        className={[
                          'rounded-full border px-2.5 py-1 text-xs font-medium transition-colors',
                          findingCategory === cat.value
                            ? 'border-forest bg-forest/10 text-forest'
                            : 'border-hairline text-navy/60 hover:bg-forest/5',
                        ].join(' ')}
                      >
                        {cat.label}
                      </button>
                    ))}
                  </div>
                  <textarea
                    required
                    value={findings}
                    onChange={(e) => setFindings(e.target.value)}
                    placeholder="What did you find during inspection?"
                    rows={3}
                    className="w-full rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest"
                  />
                  <input
                    value={actionTaken}
                    onChange={(e) => setActionTaken(e.target.value)}
                    placeholder="Action taken (optional)"
                    className="w-full rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest"
                  />
                  <button
                    type="submit"
                    disabled={isSubmittingInspection}
                    className="rounded-lg bg-forest px-4 py-2 text-sm font-bold text-white hover:bg-forest-dark disabled:opacity-60"
                  >
                    {isSubmittingInspection ? 'Saving...' : 'Save Inspection'}
                  </button>
                  {openAlert ? (
                    <p className="text-xs text-navy/40">Saving this will resolve the open alert for this house.</p>
                  ) : null}
                </form>
              ) : null}
            </div>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <TrendCard title="Mortality trend" data={trends} dataKey="mortality" color="#C8433A" Icon={Skull} goodDirection="down" />
            <TrendCard title="Feed trend (kg)" data={trends} dataKey="feed_kg" color="#C05A1D" Icon={Wheat} />
            <TrendCard title="Water trend (L)" data={trends} dataKey="water_liters" color="#6C63D6" Icon={Droplets} />
            <TrendCard title="Risk history" data={trends} dataKey="risk_score" color="#16222B" Icon={LineChart} goodDirection="down" />
          </div>

          <div className="mt-8 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
            <h2 className="text-sm font-bold text-navy">Recent Flock Checks</h2>
            <div className="mt-3 space-y-1">
              {checks.slice(0, 10).map((c) => {
                const PeriodIcon = PERIOD_ICON[c.period] || Clock3
                return (
                  <div
                    key={c.id}
                    onClick={() => navigate(`/houses/${houseId}/checks/${c.id}`)}
                    className="group flex cursor-pointer items-center gap-3 rounded-lg px-2 py-2.5 text-sm transition-colors hover:bg-forest/5"
                  >
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-bg text-navy/50">
                      <PeriodIcon size={14} />
                    </span>
                    <span className="w-36 shrink-0 text-navy/50">
                      {formatClock(c.recorded_at)} · <span className="capitalize">{c.period}</span>
                    </span>
                    <span className="flex-1 text-navy/70">Mortality {c.mortality}</span>
                    <StatusBadge status={c.risk_status} score={c.risk_score} size="sm" />
                    <ChevronRight size={15} className="shrink-0 text-navy/25 transition-transform group-hover:translate-x-0.5" />
                  </div>
                )
              })}
            </div>
          </div>

          {inspections.length > 0 ? (
            <div className="mt-4 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
              <h2 className="text-sm font-bold text-navy">Recent Inspections</h2>
              <div className="mt-3 space-y-3">
                {inspections.slice(0, 5).map((insp) => (
                  <div key={insp.id} className="border-b border-hairline pb-3 last:border-0 last:pb-0">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold capitalize text-navy">
                        {(insp.finding_category || 'inspection').replaceAll('_', ' ')}
                      </span>
                      <span className="text-xs text-navy/40">{timeAgo(insp.created_at)}</span>
                    </div>
                    <p className="mt-1 text-sm text-navy/70">{insp.findings}</p>
                    {insp.action_taken ? (
                      <p className="mt-1 text-xs text-navy/50">Action: {insp.action_taken}</p>
                    ) : null}
                    {insp.performed_by ? (
                      <p className="mt-1 text-xs text-navy/40">By {insp.performed_by}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  )
}
