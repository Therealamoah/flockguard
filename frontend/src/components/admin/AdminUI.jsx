import { useState } from 'react'
import { Loader2, X } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { PLAN_COLOR, PLAN_LABEL, pct } from '../../lib/adminFormat'

export function PageHeader({ Icon, title, subtitle, children }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
          <Icon size={20} />
        </span>
        <div>
          <h1 className="font-display text-2xl font-extrabold text-navy">{title}</h1>
          {subtitle ? <p className="text-sm text-secondary">{subtitle}</p> : null}
        </div>
      </div>
      {children}
    </div>
  )
}

export function Card({ title, action, children, className = '' }) {
  return (
    <section className={`rounded-xl border border-hairline bg-surface p-4 shadow-sm ${className}`}>
      {title ? (
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-bold text-navy">{title}</h2>
          {action}
        </div>
      ) : null}
      {children}
    </section>
  )
}

export function PlanBadge({ plan, comped }) {
  const color = PLAN_COLOR[plan] || PLAN_COLOR.pilot
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap">
      <span
        className="rounded-full px-2 py-0.5 text-xs font-bold"
        style={{ color, backgroundColor: `color-mix(in srgb, ${color} 12%, transparent)` }}
      >
        {PLAN_LABEL[plan] || plan}
      </span>
      {comped ? <span className="text-xs font-semibold text-muted">comped</span> : null}
    </span>
  )
}

export function OrgStatusBadge({ status }) {
  const suspended = status === 'suspended'
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-bold ${suspended ? 'bg-critical/10 text-critical' : 'bg-normal/10 text-normal'}`}
    >
      {suspended ? 'Suspended' : 'Active'}
    </span>
  )
}

export function UsageBar({ ratio }) {
  if (ratio === null || ratio === undefined) return <span className="text-xs text-muted">no limit</span>
  const width = Math.min(ratio, 1) * 100
  const color = ratio >= 1 ? 'var(--color-critical)' : ratio >= 0.8 ? 'var(--color-warning)' : 'var(--color-forest)'
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-hairline">
        <div className="h-full rounded-full" style={{ width: `${width}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs font-semibold tabular-nums text-secondary">{pct(ratio)}</span>
    </div>
  )
}

export function LoadingBlock() {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-sm text-secondary">
      <Loader2 size={16} className="animate-spin" />
      Loading...
    </div>
  )
}

export function ErrorBlock({ message, onRetry }) {
  return (
    <div className="mt-4 rounded-xl border border-critical/30 bg-critical/5 p-4 text-sm text-critical">
      {message}{' '}
      {onRetry ? (
        <button onClick={onRetry} className="font-bold underline">
          Retry
        </button>
      ) : null}
    </div>
  )
}

// Every admin write needs a human reason - it's stored in the audit log.
export function ReasonDialog({ title, description, confirmLabel, danger, onConfirm, onClose, children }) {
  const [reason, setReason] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setIsSaving(true)
    setError('')
    try {
      await onConfirm(reason.trim())
      onClose()
    } catch (err) {
      setError(err.detail || 'That did not work. Please try again.')
      setIsSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <form
        onSubmit={handleSubmit}
        className="relative w-full max-w-md rounded-xl border border-hairline bg-surface p-5 shadow-xl"
      >
        <div className="flex items-start justify-between gap-3">
          <h2 className="font-display text-lg font-extrabold text-navy">{title}</h2>
          <button type="button" onClick={onClose} className="text-muted hover:text-navy" aria-label="Close">
            <X size={18} />
          </button>
        </div>
        {description ? <p className="mt-1 text-sm text-secondary">{description}</p> : null}
        {children}
        <label className="mb-1 mt-4 block text-xs font-semibold text-secondary">Reason (saved to the audit log)</label>
        <textarea
          required
          minLength={3}
          maxLength={500}
          rows={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="w-full rounded-lg border border-hairline bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-forest"
        />
        {error ? <p className="mt-2 text-sm text-critical">{error}</p> : null}
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg px-4 py-2 text-sm font-semibold text-secondary hover:text-navy"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSaving || reason.trim().length < 3}
            className={`rounded-lg px-4 py-2 text-sm font-bold text-white disabled:opacity-60 ${
              danger ? 'bg-critical hover:opacity-90' : 'bg-forest hover:bg-forest-dark'
            }`}
          >
            {isSaving ? 'Saving...' : confirmLabel}
          </button>
        </div>
      </form>
    </div>
  )
}

const axisProps = { tick: { fill: 'var(--color-muted)', fontSize: 11 }, tickLine: false, axisLine: false }

function CountTooltip({ active, payload, label, noun }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-hairline bg-surface px-3 py-2 text-xs shadow-md">
      <p className="text-muted">{label}</p>
      <p className="mt-0.5 font-semibold text-navy">
        {payload[0].value} {noun}
      </p>
    </div>
  )
}

export function CountBars({ data, xKey, noun, color, tickFormatter }) {
  return (
    <div className="h-44">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--color-hairline)" strokeDasharray="3 3" />
          <XAxis dataKey={xKey} tickFormatter={tickFormatter} minTickGap={16} {...axisProps} />
          <YAxis width={28} allowDecimals={false} {...axisProps} />
          <Tooltip cursor={{ fill: 'var(--color-hairline)', opacity: 0.4 }} content={<CountTooltip noun={noun} />} />
          <Bar dataKey="count" fill={color} radius={[4, 4, 0, 0]} maxBarSize={22} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

const LIMIT_FIELDS = [
  { key: 'houses', label: 'Houses' },
  { key: 'birds', label: 'Birds' },
  { key: 'team_members', label: 'Team seats' },
  { key: 'ai_requests_monthly', label: 'AI requests / month' },
]

export function PlanOverrideFields({ form, setForm }) {
  return (
    <div className="mt-4 space-y-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex-1">
          <label className="mb-1 block text-xs font-semibold text-secondary">Plan</label>
          <select
            value={form.plan}
            onChange={(e) => setForm({ ...form, plan: e.target.value })}
            className="w-full rounded-lg border border-hairline bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-forest"
          >
            {Object.entries(PLAN_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </div>
        <label className="flex items-center gap-2 pb-2 text-sm text-navy">
          <input
            type="checkbox"
            checked={form.comped}
            onChange={(e) => setForm({ ...form, comped: e.target.checked })}
          />
          Comped (free)
        </label>
      </div>
      <div>
        <p className="mb-1 text-xs font-semibold text-secondary">
          Custom limits {form.plan === 'enterprise' ? '(required)' : "(optional - blank keeps the plan's default)"}
        </p>
        <div className="grid grid-cols-2 gap-2">
          {LIMIT_FIELDS.map(({ key, label }) => (
            <input
              key={key}
              type="number"
              min={0}
              placeholder={label}
              value={form.limits[key] ?? ''}
              onChange={(e) => setForm({ ...form, limits: { ...form.limits, [key]: e.target.value } })}
              className="rounded-lg border border-hairline bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-forest"
            />
          ))}
        </div>
      </div>
      <p className="text-xs text-muted">
        This changes FlockGuard only. If the org has a live Paystack subscription, cancel it in Paystack first or its
        next webhook may change the plan back.
      </p>
    </div>
  )
}
