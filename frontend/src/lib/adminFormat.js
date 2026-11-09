export const PLAN_LABEL = { pilot: 'Pilot', starter: 'Starter', growth: 'Growth', pro: 'Pro', enterprise: 'Enterprise' }

export const PLAN_COLOR = {
  pilot: 'var(--color-muted)',
  starter: 'var(--color-series-1)',
  growth: 'var(--color-series-3)',
  pro: 'var(--color-ai)',
  enterprise: 'var(--color-forest)',
}

export const ghs = (n) => `GH₵${Number(n || 0).toLocaleString()}`
export const pct = (ratio) => (ratio === null || ratio === undefined ? '—' : `${Math.round(ratio * 100)}%`)
export const shortDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' }) : '—'
export const dateTime = (iso) =>
  iso ? new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '—'
export const dayLabel = (d) => new Date(`${d}T00:00:00`).toLocaleDateString([], { month: 'short', day: 'numeric' })

// PlanOverrideFields keeps limits as strings while typing - blank = "keep the
// plan's default", so only filled-in fields are sent.
export function limitsFromForm(formLimits) {
  const limits = Object.fromEntries(
    Object.entries(formLimits)
      .filter(([, v]) => v !== '' && v !== undefined && v !== null)
      .map(([k, v]) => [k, Number(v)]),
  )
  return Object.keys(limits).length ? limits : null
}
