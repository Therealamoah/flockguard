import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Briefcase, ChevronDown, ChevronUp, Crown, Mail, MessageCircle, Phone, RefreshCw, Sparkles } from 'lucide-react'
import StatCard from '../../components/StatCard'
import { api } from '../../lib/api'
import { timeAgo } from '../../lib/time'
import {
  Card,
  ErrorBlock,
  LoadingBlock,
  PageHeader,
  PlanBadge,
  PlanOverrideFields,
  ReasonDialog,
  UsageBar,
} from '../../components/admin/AdminUI'
import { dateTime, limitsFromForm } from '../../lib/adminFormat'
import { useAdminData } from '../../lib/useAdminData'

const STATUSES = [
  { value: 'new', label: 'New', className: 'bg-warning/10 text-warning' },
  { value: 'contacted', label: 'Contacted', className: 'bg-ai/10 text-ai' },
  { value: 'won', label: 'Won', className: 'bg-normal/10 text-normal' },
  { value: 'lost', label: 'Lost', className: 'bg-hairline text-muted' },
]
const STATUS_META = Object.fromEntries(STATUSES.map((s) => [s.value, s]))
const CONTACT_ICON = { call: Phone, whatsapp: MessageCircle, email: Mail }

function StatusPill({ status }) {
  const meta = STATUS_META[status] || STATUS_META.new
  return <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${meta.className}`}>{meta.label}</span>
}

function LeadDetails({ lead, onChanged, onGrant }) {
  const [note, setNote] = useState('')
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')

  async function save(update) {
    setIsSaving(true)
    setError('')
    try {
      await api.admin.updateEnterpriseLead(lead.id, update)
      setNote('')
      onChanged()
    } catch (err) {
      setError(err.detail || 'Could not save that.')
    } finally {
      setIsSaving(false)
    }
  }

  const ContactIcon = CONTACT_ICON[lead.contact_method] || Mail
  const usage = lead.usage || {}
  const requested = lead.requested || {}

  return (
    <div className="space-y-4 bg-bg/60 px-4 py-4">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="text-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Contact</p>
          <p className="mt-1 font-semibold text-navy">{lead.display_name || lead.email}</p>
          {lead.email ? (
            <a href={`mailto:${lead.email}`} className="block text-xs text-forest hover:underline">
              {lead.email}
            </a>
          ) : null}
          {lead.phone ? <p className="text-xs text-secondary">{lead.phone}</p> : null}
          <p className="mt-1 flex items-center gap-1 text-xs capitalize text-secondary">
            <ContactIcon size={12} /> prefers {lead.contact_method}
          </p>
        </div>
        <div className="text-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Today vs. wants</p>
          <p className="mt-1 text-secondary">
            <b className="text-navy">{usage.houses ?? 0}</b> → {requested.houses ?? '?'} houses
          </p>
          <p className="text-secondary">
            <b className="text-navy">{(usage.birds ?? 0).toLocaleString()}</b> → {requested.birds?.toLocaleString() ?? '?'}{' '}
            birds
          </p>
          <p className="text-xs text-muted">
            {usage.team_members ?? 0} team members · {usage.ai_requests_month ?? 0} AI requests this month
          </p>
        </div>
        <div className="text-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted">Message</p>
          <p className="mt-1 whitespace-pre-wrap text-secondary">{lead.message || '—'}</p>
        </div>
      </div>

      {lead.notes?.length ? (
        <ul className="space-y-1.5">
          {lead.notes.map((n, i) => (
            <li key={i} className="rounded-lg border border-hairline bg-surface px-3 py-2 text-sm">
              <span className="text-secondary">{n.text}</span>
              <span className="mt-0.5 block text-xs text-muted">
                {n.by} · {dateTime(n.at)}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="flex flex-wrap items-end gap-2">
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          maxLength={1000}
          placeholder="Add a note (e.g. called, sent proposal)..."
          className="min-w-[200px] flex-1 rounded-lg border border-hairline bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-forest"
        />
        <button
          onClick={() => save({ note: note.trim() })}
          disabled={isSaving || !note.trim()}
          className="rounded-lg border border-hairline bg-surface px-3 py-2 text-sm font-semibold text-navy hover:border-forest disabled:opacity-50"
        >
          Add note
        </button>
        <select
          value={lead.status}
          disabled={isSaving}
          onChange={(e) => save({ status: e.target.value, ...(note.trim() ? { note: note.trim() } : {}) })}
          className="rounded-lg border border-hairline bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-forest"
          aria-label="Lead status"
        >
          {STATUSES.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        {lead.org_plan_now !== 'enterprise' ? (
          <button
            onClick={() => onGrant(lead)}
            className="flex items-center gap-1.5 rounded-lg bg-forest px-3 py-2 text-sm font-bold text-white hover:bg-forest-dark"
          >
            <Crown size={14} />
            Grant Enterprise
          </button>
        ) : (
          <span className="text-xs font-semibold text-normal">Already on Enterprise</span>
        )}
      </div>
      {error ? <p className="text-sm text-critical">{error}</p> : null}
    </div>
  )
}

export default function AdminEnterprisePage() {
  const { data, error, isLoading, reload } = useAdminData(api.admin.enterprise)
  const [filter, setFilter] = useState('open')
  const [expanded, setExpanded] = useState(null)
  const [grant, setGrant] = useState(null) // { orgId, leadId, name }
  const [planForm, setPlanForm] = useState(null)

  function openGrant({ orgId, leadId, name, houses, birds }) {
    setPlanForm({
      plan: 'enterprise',
      comped: false,
      limits: { houses: houses ?? '', birds: birds ?? '', team_members: '', ai_requests_monthly: '' },
    })
    setGrant({ orgId, leadId, name })
  }

  async function submitGrant(reason) {
    await api.admin.overrideSubscription(grant.orgId, {
      plan: planForm.plan,
      comped: planForm.comped,
      limits: limitsFromForm(planForm.limits),
      reason,
    })
    if (grant.leadId) await api.admin.updateEnterpriseLead(grant.leadId, { status: 'won', note: `Granted: ${reason}` })
    reload()
  }

  const leads = data?.leads ?? []
  const visible = leads.filter((l) =>
    filter === 'all' ? true : filter === 'open' ? ['new', 'contacted'].includes(l.status) : l.status === filter,
  )

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 lg:p-6">
      <PageHeader
        Icon={Briefcase}
        title="Enterprise"
        subtitle="Who asked for Enterprise, where each deal stands, and who to offer it to."
      >
        <button
          onClick={reload}
          className="flex items-center gap-1.5 rounded-lg border border-hairline bg-surface px-3 py-2 text-sm font-semibold text-secondary hover:text-navy"
        >
          <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </PageHeader>

      {error ? <ErrorBlock message={error} onRetry={reload} /> : null}
      {!data && isLoading ? <LoadingBlock /> : null}

      {data ? (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {STATUSES.map((s) => (
              <button key={s.value} onClick={() => setFilter(s.value)} className="text-left">
                <StatCard label={s.label} value={data.counts[s.value]} Icon={s.value === 'won' ? Crown : Briefcase} />
              </button>
            ))}
          </div>

          <Card
            title="Requests"
            action={
              <div className="flex flex-wrap gap-1">
                {[{ value: 'open', label: 'Open' }, ...STATUSES, { value: 'all', label: 'All' }].map((f) => (
                  <button
                    key={f.value}
                    onClick={() => setFilter(f.value)}
                    className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                      filter === f.value ? 'bg-forest text-white' : 'text-secondary hover:bg-forest/5'
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            }
          >
            {visible.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted">
                {leads.length === 0
                  ? 'No Enterprise requests yet. Owners send them from the Billing page.'
                  : 'No requests match this filter.'}
              </p>
            ) : (
              <div className="-mx-4 divide-y divide-hairline border-y border-hairline">
                {visible.map((lead) => {
                  const open = expanded === lead.id
                  return (
                    <div key={lead.id}>
                      <button
                        onClick={() => setExpanded(open ? null : lead.id)}
                        className="flex w-full flex-wrap items-center gap-3 px-4 py-3 text-left hover:bg-forest/5"
                      >
                        <div className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-semibold text-navy">
                            {lead.farm_name || 'No farm name'}
                          </span>
                          <span className="block truncate text-xs text-muted">{lead.display_name || lead.email}</span>
                        </div>
                        <PlanBadge plan={lead.org_plan_now || lead.current_plan} />
                        <span className="w-28 text-xs text-secondary">
                          wants {lead.requested?.houses ?? '?'} houses
                        </span>
                        <span className="w-20 text-xs text-muted">{timeAgo(lead.created_at)}</span>
                        <StatusPill status={lead.status} />
                        {open ? <ChevronUp size={16} className="text-muted" /> : <ChevronDown size={16} className="text-muted" />}
                      </button>
                      {open ? (
                        <LeadDetails
                          lead={lead}
                          onChanged={reload}
                          onGrant={(l) =>
                            openGrant({
                              orgId: l.org_id,
                              leadId: l.id,
                              name: l.farm_name || l.email,
                              houses: l.requested?.houses,
                              birds: l.requested?.birds,
                            })
                          }
                        />
                      ) : null}
                    </div>
                  )
                })}
              </div>
            )}
          </Card>

          <Card
            title={
              <span className="flex items-center gap-2">
                <Sparkles size={14} className="text-ai" />
                Upgrade candidates
              </span>
            }
            action={<span className="text-xs text-muted">big operations, or Growth/Pro orgs near their limits</span>}
          >
            {data.candidates.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted">No organization stands out for Enterprise yet.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-sm">
                  <thead className="text-left text-xs text-muted">
                    <tr>
                      <th className="pb-2 font-semibold">Organization</th>
                      <th className="pb-2 font-semibold">Plan</th>
                      <th className="pb-2 font-semibold">Why</th>
                      <th className="pb-2 font-semibold">Houses</th>
                      <th className="pb-2 font-semibold">AI</th>
                      <th className="pb-2" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-hairline">
                    {data.candidates.map((c) => (
                      <tr key={c.org_id}>
                        <td className="py-2.5 pr-3">
                          <Link to={`/admin/orgs/${c.org_id}`} className="font-semibold text-navy hover:text-forest">
                            {c.farm_name || c.owner_email || c.org_id}
                          </Link>
                          <span className="block text-xs text-muted">{c.owner_email}</span>
                        </td>
                        <td className="py-2.5 pr-3">
                          <PlanBadge plan={c.plan} />
                        </td>
                        <td className="py-2.5 pr-3">
                          <div className="flex flex-wrap gap-1">
                            {c.reasons.map((r) => (
                              <span
                                key={r}
                                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                                  r === 'asked for Enterprise' ? 'bg-warning/10 text-warning' : 'bg-hairline text-secondary'
                                }`}
                              >
                                {r}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="py-2.5 pr-3">
                          <UsageBar ratio={c.house_usage_ratio} />
                        </td>
                        <td className="py-2.5 pr-3">
                          <UsageBar ratio={c.ai_usage_ratio} />
                        </td>
                        <td className="py-2.5 text-right">
                          <button
                            onClick={() =>
                              openGrant({ orgId: c.org_id, name: c.farm_name || c.owner_email, houses: c.houses || '' })
                            }
                            className="inline-flex items-center gap-1 whitespace-nowrap text-xs font-bold text-forest hover:underline"
                          >
                            <Crown size={12} />
                            Grant
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </>
      ) : null}

      {grant ? (
        <ReasonDialog
          title={`Grant Enterprise to ${grant.name}`}
          description="Sets this organization's plan and limits right away. Enterprise needs at least one custom limit."
          confirmLabel="Grant plan"
          onConfirm={submitGrant}
          onClose={() => setGrant(null)}
        >
          <PlanOverrideFields form={planForm} setForm={setPlanForm} />
        </ReasonDialog>
      ) : null}
    </div>
  )
}
