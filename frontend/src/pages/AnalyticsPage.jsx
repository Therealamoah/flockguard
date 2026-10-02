import { useEffect, useMemo, useState } from 'react'
import { BarChart3, CalendarDays, Droplets, Inbox, LineChart, Loader2, Skull, TrendingDown, TrendingUp, Wheat } from 'lucide-react'
import { api } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import { STATUS_META } from '../lib/risk'
import { FACTOR_LABELS, FACTOR_ORDER } from '../lib/checkLabels'
import TimeChart from '../components/TimeChart'
import BreakdownCard from '../components/BreakdownCard'
import StatusBadge from '../components/StatusBadge'

const RANGES = [7, 14, 30]
const DAY_MS = 86400000

// 'YYYY-MM-DD' in the viewer's local time (what <input type="date"> uses).
const toDateInput = (ms) => {
  const d = new Date(ms)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
const fromDateInput = (value, endOfDay = false) => new Date(`${value}T${endOfDay ? '23:59:59.999' : '00:00:00'}`).getTime()
const prettyDate = (value) => new Date(`${value}T00:00:00`).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })

// Status colors come from the theme tokens so they switch with dark mode.
const STATUS_COLORS = {
  normal: 'var(--color-normal)',
  watch: 'var(--color-watch)',
  warning: 'var(--color-warning)',
  critical: 'var(--color-critical)',
}
const RISK_THRESHOLDS = [
  { value: 25, label: 'Watch', color: STATUS_COLORS.watch },
  { value: 50, label: 'Warning', color: STATUS_COLORS.warning },
  { value: 75, label: 'Critical', color: STATUS_COLORS.critical },
]

const sum = (rows, key) => rows.reduce((total, r) => total + (r[key] ?? 0), 0)
function average(rows, key) {
  const values = rows.map((r) => r[key]).filter((v) => v != null)
  return values.length ? Math.round((values.reduce((a, b) => a + b, 0) / values.length) * 10) / 10 : null
}

// "+3 vs the 7 days before" - goodDirection decides whether up reads as
// better (green) or worse (red). Text stays in text tokens; the arrow and
// word carry the meaning, so it never relies on color alone.
function Change({ now, before, days, goodDirection = 'down' }) {
  if (now == null || before == null) return <p className="mt-1 text-xs text-muted">Not enough past checks to compare</p>
  const diff = Math.round((now - before) * 10) / 10
  if (diff === 0) return <p className="mt-1 text-xs text-muted">Same as the {days} days before</p>
  const better = goodDirection === 'down' ? diff < 0 : diff > 0
  const Icon = diff > 0 ? TrendingUp : TrendingDown
  return (
    <p className={`mt-1 flex items-center gap-1 text-xs font-semibold ${better ? 'text-normal' : 'text-critical'}`}>
      <Icon size={13} />
      {diff > 0 ? '+' : ''}
      {diff} vs the {days} days before
      <span className="sr-only">{better ? '(better)' : '(worse)'}</span>
    </p>
  )
}

function Kpi({ label, Icon, value, unit, children }) {
  return (
    <div className="rounded-xl border border-hairline bg-surface p-4 shadow-sm">
      <p className="flex items-center gap-1.5 text-xs font-semibold text-secondary">
        <Icon size={14} className="text-muted" />
        {label}
      </p>
      <p className="mt-2 font-display text-3xl font-extrabold leading-none text-navy">
        {value ?? '—'}
        {value != null && unit ? <span className="ml-1 text-sm font-semibold text-muted">{unit}</span> : null}
      </p>
      {children}
    </div>
  )
}

function ChartCard({ title, Icon, children, className = '' }) {
  return (
    <div className={`rounded-xl border border-hairline bg-surface p-5 shadow-sm ${className}`}>
      <h2 className="flex items-center gap-2 text-sm font-bold text-navy">
        <Icon size={15} className="text-muted" />
        {title}
      </h2>
      <div className="mt-3">{children}</div>
    </div>
  )
}

export default function AnalyticsPage() {
  const { currentFarmId, houses } = useAppStore()
  const [pickedHouseId, setPickedHouseId] = useState('')
  // A preset number of days, or 'custom' with the farmer's own From/To dates.
  const [days, setDays] = useState(14)
  const [custom, setCustom] = useState({ from: '', to: '', today: '' })
  // The window the data was fetched for travels with it, so the charts
  // always describe exactly what was loaded.
  const [loaded, setLoaded] = useState({ key: null, trends: [], start: 0, end: 0 })

  const houseId = pickedHouseId || houses[0]?.id || ''
  const isCustom = days === 'custom'
  const customError =
    isCustom && custom.from && custom.to && custom.from > custom.to ? 'The "From" date must be before the "To" date.' : ''
  const customReady = isCustom && custom.from && custom.to && !customError
  const rangeKey = isCustom ? (customReady ? `custom:${custom.from}:${custom.to}` : null) : `last:${days}`
  const requestKey = currentFarmId && houseId && rangeKey ? `${currentFarmId}/${houseId}/${rangeKey}` : null

  useEffect(() => {
    if (!requestKey) return
    let cancelled = false
    const end = isCustom ? fromDateInput(custom.to, true) : Date.now()
    const start = isCustom ? fromDateInput(custom.from) : end - days * DAY_MS
    // Also fetch the same-length period before, for the "vs before" comparisons.
    const fetchStart = start - (end - start)
    api.analytics
      .houseTrendsBetween(currentFarmId, houseId, new Date(fetchStart), new Date(end))
      .then((data) => {
        if (!cancelled) setLoaded({ key: requestKey, trends: data, start, end })
      })
      .catch(() => {
        if (!cancelled) setLoaded({ key: requestKey, trends: [], start, end })
      })
    return () => {
      cancelled = true
    }
    // requestKey already encodes the house, range and custom dates.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestKey])

  function openCustom() {
    const today = Date.now()
    setCustom((prev) => ({
      from: prev.from || toDateInput(today - 6 * DAY_MS),
      to: prev.to || toDateInput(today),
      today: toDateInput(today),
    }))
    setDays('custom')
  }

  const isLoading = requestKey != null && loaded.key !== requestKey
  const rangeDays = Math.max(1, Math.round((loaded.end - loaded.start) / DAY_MS))
  const rangeLabel = isCustom ? `${prettyDate(custom.from)} – ${prettyDate(custom.to)}` : `the last ${days} days`

  const view = useMemo(() => {
    const { start, end } = loaded
    const prevStart = start - (end - start)
    const at = (r) => new Date(r.recorded_at).getTime()
    const current = loaded.trends.filter((r) => at(r) >= start && at(r) <= end)
    const previous = loaded.trends.filter((r) => at(r) >= prevStart && at(r) < start)

    const statusCounts = Object.keys(STATUS_META).map((status) => ({
      key: status,
      label: STATUS_META[status].label,
      value: current.filter((r) => r.risk_status === status).length,
      color: STATUS_COLORS[status],
    }))
    const factorCounts = FACTOR_ORDER.map((key, i) => ({
      key,
      label: FACTOR_LABELS[key],
      value: current.filter((r) => (r.risk_factor_keys || []).includes(key)).length,
      color: `var(--color-series-${i + 1})`,
    }))

    return {
      current,
      previous,
      latest: current[current.length - 1] || null,
      hasPrevious: previous.length > 0,
      statusCounts,
      factorCounts,
      hasWater: current.some((r) => r.water_liters != null),
    }
  }, [loaded])

  const { current, previous, latest, hasPrevious } = view
  const prevOr = (value) => (hasPrevious ? value : null)

  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-ai/10 text-ai">
            <BarChart3 size={20} />
          </span>
          <div>
            <h1 className="font-display text-2xl font-extrabold text-navy">Trends</h1>
            <p className="text-sm text-secondary">See how one house is doing over time.</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex gap-1 rounded-lg border border-hairline bg-surface p-1" role="group" aria-label="Time range">
            {RANGES.map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDays(d)}
                aria-pressed={days === d}
                className={[
                  'rounded-md px-3 py-1.5 text-xs font-semibold transition-colors',
                  days === d ? 'bg-forest text-white' : 'text-secondary hover:bg-forest/5',
                ].join(' ')}
              >
                {d} days
              </button>
            ))}
            <button
              type="button"
              onClick={openCustom}
              aria-pressed={isCustom}
              className={[
                'flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors',
                isCustom ? 'bg-forest text-white' : 'text-secondary hover:bg-forest/5',
              ].join(' ')}
            >
              <CalendarDays size={13} />
              Custom
            </button>
          </div>
          <select
            value={houseId}
            onChange={(e) => setPickedHouseId(e.target.value)}
            aria-label="House"
            className="rounded-lg border border-hairline bg-surface px-3 py-2 text-sm outline-none focus:border-forest"
          >
            {houses.map((h) => (
              <option key={h.id} value={h.id}>
                {h.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {isCustom ? (
        <div className="mt-4 flex flex-wrap items-end gap-3 rounded-xl border border-hairline bg-surface p-4 shadow-sm">
          <label className="text-xs font-semibold text-secondary">
            From
            <input
              type="date"
              value={custom.from}
              max={custom.to || custom.today}
              onChange={(e) => setCustom((c) => ({ ...c, from: e.target.value }))}
              className="mt-1 block rounded-lg border border-hairline bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-forest"
            />
          </label>
          <label className="text-xs font-semibold text-secondary">
            To
            <input
              type="date"
              value={custom.to}
              min={custom.from || undefined}
              max={custom.today}
              onChange={(e) => setCustom((c) => ({ ...c, to: e.target.value }))}
              className="mt-1 block rounded-lg border border-hairline bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-forest"
            />
          </label>
          {customError ? <p className="pb-2 text-sm text-critical">{customError}</p> : null}
        </div>
      ) : null}

      {isCustom && !customReady ? (
        <div className="mt-6 flex flex-col items-center gap-2 rounded-xl border border-hairline bg-surface py-16 text-center shadow-sm">
          <CalendarDays size={28} className="text-muted" />
          <p className="text-sm text-secondary">{customError || 'Pick a "From" and "To" date to see your trends.'}</p>
        </div>
      ) : isLoading ? (
        <div className="mt-6 flex items-center justify-center gap-2 rounded-xl border border-hairline bg-surface py-16 text-sm text-secondary shadow-sm">
          <Loader2 size={16} className="animate-spin" />
          Getting trends...
        </div>
      ) : current.length === 0 ? (
        <div className="mt-6 flex flex-col items-center gap-2 rounded-xl border border-hairline bg-surface py-16 text-center shadow-sm">
          <Inbox size={28} className="text-muted" />
          <p className="text-sm text-secondary">
            No checks in {rangeLabel}.
          </p>
        </div>
      ) : (
        <>
          <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Kpi label="Risk now" Icon={LineChart} value={latest?.risk_score} unit="/ 100">
              <div className="mt-2">
                <StatusBadge status={latest?.risk_status} size="sm" />
              </div>
            </Kpi>
            <Kpi label="Dead birds" Icon={Skull} value={sum(current, 'mortality')}>
              <Change now={sum(current, 'mortality')} before={prevOr(sum(previous, 'mortality'))} days={rangeDays} />
            </Kpi>
            <Kpi label="Feed per check" Icon={Wheat} value={average(current, 'feed_kg')} unit="kg">
              <Change now={average(current, 'feed_kg')} before={prevOr(average(previous, 'feed_kg'))} days={rangeDays} goodDirection="up" />
            </Kpi>
            <Kpi label="Water per check" Icon={Droplets} value={average(current, 'water_liters')} unit="L">
              {view.hasWater ? (
                <Change now={average(current, 'water_liters')} before={prevOr(average(previous, 'water_liters'))} days={rangeDays} goodDirection="up" />
              ) : (
                <p className="mt-1 text-xs text-muted">Not measured in litres yet</p>
              )}
            </Kpi>
          </div>

          <ChartCard title="Risk over time" Icon={LineChart} className="mt-4">
            <TimeChart
              data={current}
              dataKey="risk_score"
              valueLabel="Risk"
              color="var(--color-navy)"
              height={260}
              yDomain={[0, 100]}
              thresholds={RISK_THRESHOLDS}
            />
          </ChartCard>

          <div className="mt-4 grid gap-4 lg:grid-cols-3">
            <ChartCard title="Dead birds per check" Icon={Skull}>
              <TimeChart data={current} dataKey="mortality" kind="bar" valueLabel="Dead birds" color="var(--color-series-2)" />
            </ChartCard>
            <ChartCard title="Feed eaten (kg)" Icon={Wheat}>
              <TimeChart data={current} dataKey="feed_kg" valueLabel="Feed" unit="kg" color="var(--color-series-4)" />
            </ChartCard>
            <ChartCard title="Water drunk (litres)" Icon={Droplets}>
              {view.hasWater ? (
                <TimeChart data={current} dataKey="water_liters" valueLabel="Water" unit="L" color="var(--color-series-1)" />
              ) : (
                <p className="flex h-45 items-center justify-center text-center text-sm text-secondary">
                  No water readings in litres in {rangeLabel}.
                </p>
              )}
            </ChartCard>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <BreakdownCard
              title="How the checks went"
              subtitle={`Risk level of each check in ${rangeLabel}`}
              items={view.statusCounts}
              unitLabel="checks"
              emptyText="No checks yet."
            />
            <BreakdownCard
              title="What raised the risk"
              subtitle="How many checks found each problem"
              items={view.factorCounts}
              unitLabel="problems"
              emptyText={`No problems found in ${rangeLabel}.`}
            />
          </div>
        </>
      )}
    </div>
  )
}
