import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Building2, Ban, CircleCheck, CreditCard, Rocket, UserX, UserCheck } from 'lucide-react'
import StatusBadge from '../../components/StatusBadge'
import { api } from '../../lib/api'
import { timeAgo } from '../../lib/time'
import {
  Card,
  ErrorBlock,
  LoadingBlock,
  OrgStatusBadge,
  PageHeader,
  PlanBadge,
  PlanOverrideFields,
  ReasonDialog,
  UsageBar,
} from '../../components/admin/AdminUI'
import { dateTime, ghs, limitsFromForm, shortDate } from '../../lib/adminFormat'
import { useAdminData } from '../../lib/useAdminData'
import UpgradeOfferDialog from '../../components/admin/UpgradeOfferDialog'

function Metric({ label, value, children }) {
  return (
    <div className="rounded-lg border border-hairline bg-surface p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 font-display text-lg font-extrabold text-navy">{value}</p>
      {children}
    </div>
  )
}

export default function AdminOrgDetailPage() {
  const { orgId } = useParams()
  const { data: org, error, isLoading, reload } = useAdminData(api.admin.org, orgId)
  const [dialog, setDialog] = useState(null)
  const [planForm, setPlanForm] = useState(null)

  function openPlanDialog() {
    setPlanForm({ plan: org.plan, comped: org.comped, limits: {} })
    setDialog({ kind: 'plan' })
  }

  async function submitPlan(reason) {
    await api.admin.overrideSubscription(orgId, {
      plan: planForm.plan,
      comped: planForm.comped,
      limits: limitsFromForm(planForm.limits),
      reason,
    })
    reload()
  }

  if (!org) {
    return (
      <div className="mx-auto max-w-6xl p-4 lg:p-6">
        <BackLink />
        {error ? <ErrorBlock message={error} onRetry={reload} /> : null}
        {isLoading ? <LoadingBlock /> : null}
      </div>
    )
  }

  const suspended = org.platform_status === 'suspended'
  const sub = org.subscription
  const houseName = Object.fromEntries(org.farms.flatMap((f) => f.houses.map((h) => [h.id, h.name])))

  return (
    <div className="mx-auto max-w-6xl space-y-5 p-4 lg:p-6">
      <BackLink />
      <PageHeader
        Icon={Building2}
        title={org.farms[0]?.name || 'No farm yet'}
        subtitle={`${org.owner_email || 'No owner'} · ${org.org_id}`}
      >
        <div className="flex flex-wrap items-center gap-2">
          <OrgStatusBadge status={org.platform_status} />
          <button
            onClick={() => setDialog({ kind: 'offer' })}
            className="flex items-center gap-1.5 rounded-lg bg-forest px-3 py-2 text-sm font-bold text-white hover:bg-forest-dark"
            title="Email the owner a suggested plan - they upgrade and pay themselves"
          >
            <Rocket size={14} />
            Offer upgrade
          </button>
          <button
            onClick={openPlanDialog}
            className="flex items-center gap-1.5 rounded-lg border border-hairline bg-surface px-3 py-2 text-sm font-semibold text-navy hover:border-forest"
            title="Switch the plan right away, with no payment"
          >
            <CreditCard size={14} />
            Change plan
          </button>
          {suspended ? (
            <button
              onClick={() => setDialog({ kind: 'reactivate' })}
              className="flex items-center gap-1.5 rounded-lg bg-forest px-3 py-2 text-sm font-bold text-white hover:bg-forest-dark"
            >
              <CircleCheck size={14} />
              Reactivate
            </button>
          ) : (
            <button
              onClick={() => setDialog({ kind: 'suspend' })}
              className="flex items-center gap-1.5 rounded-lg bg-critical px-3 py-2 text-sm font-bold text-white hover:opacity-90"
            >
              <Ban size={14} />
              Suspend
            </button>
          )}
        </div>
      </PageHeader>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <Metric label="Plan" value={<PlanBadge plan={org.plan} comped={org.comped} />}>
          <p className="mt-1 text-xs text-muted">
            {ghs(sub.price_ghs)}/mo · {sub.status}
          </p>
        </Metric>
        <Metric label="Houses" value={`${org.houses} / ${org.limits.houses ?? '∞'}`}>
          <div className="mt-1">
            <UsageBar ratio={org.house_usage_ratio} />
          </div>
        </Metric>
        <Metric label="Birds" value={`${org.usage.birds.toLocaleString()}`}>
          <p className="mt-1 text-xs text-muted">limit {org.limits.birds?.toLocaleString() ?? '∞'}</p>
        </Metric>
        <Metric label="AI requests" value={`${org.ai_requests_month} / ${org.limits.ai_requests_monthly ?? '∞'}`}>
          <div className="mt-1">
            <UsageBar ratio={org.ai_usage_ratio} />
          </div>
        </Metric>
        <Metric label="Checks (7d / 30d)" value={`${org.checks_7d} / ${org.checks_30d}`}>
          <p className="mt-1 text-xs text-muted">last {timeAgo(org.last_check_at) || 'never'}</p>
        </Metric>
        <Metric label="Storage" value={`${org.usage.storage_mb} MB`}>
          <p className="mt-1 text-xs text-muted">joined {shortDate(org.created_at)}</p>
        </Metric>
      </div>

      <OfferStatus org={org} onWithdrawn={reload} />

      {sub.admin_override ? (
        <p className="rounded-lg border border-ai/30 bg-ai/5 px-3 py-2 text-xs text-secondary">
          Plan last set manually by <b>{sub.admin_override.by}</b> {timeAgo(sub.admin_override.at)}: “
          {sub.admin_override.reason}”
        </p>
      ) : null}

      <Card title={`Team (${org.members.length})`}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="text-left text-xs text-muted">
              <tr>
                <th className="pb-2 font-semibold">Person</th>
                <th className="pb-2 font-semibold">Role</th>
                <th className="pb-2 font-semibold">Membership</th>
                <th className="pb-2 font-semibold">Login</th>
                <th className="pb-2 font-semibold">Last active</th>
                <th className="pb-2 font-semibold">Last sign-in</th>
                <th className="pb-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline">
              {org.members.map((m) => (
                <tr key={m.id}>
                  <td className="py-2.5 pr-3">
                    <span className="block font-semibold text-navy">{m.display_name || m.email}</span>
                    <span className="block text-xs text-muted">{m.email}</span>
                  </td>
                  <td className="py-2.5 pr-3 capitalize text-secondary">{m.role}</td>
                  <td className="py-2.5 pr-3 capitalize text-secondary">{m.status}</td>
                  <td className="py-2.5 pr-3">
                    {!m.account.exists ? (
                      <span className="text-xs text-muted">no account</span>
                    ) : m.account.disabled ? (
                      <span className="text-xs font-bold text-critical">Disabled</span>
                    ) : (
                      <span className="text-xs font-bold text-normal">Enabled</span>
                    )}
                  </td>
                  <td className="py-2.5 pr-3 text-xs font-semibold text-navy">{timeAgo(m.last_seen_at) || '—'}</td>
                  <td className="py-2.5 pr-3 text-xs text-secondary">{timeAgo(m.account.last_sign_in_at) || '—'}</td>
                  <td className="py-2.5 text-right">
                    {m.account.exists ? (
                      <button
                        onClick={() => setDialog({ kind: m.account.disabled ? 'enable' : 'disable', member: m })}
                        className="inline-flex items-center gap-1 text-xs font-bold text-secondary hover:text-navy"
                      >
                        {m.account.disabled ? <UserCheck size={13} /> : <UserX size={13} />}
                        {m.account.disabled ? 'Enable' : 'Disable'}
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Farms & houses">
          {org.farms.length === 0 ? <p className="text-sm text-muted">This org hasn't finished onboarding.</p> : null}
          <ul className="space-y-3">
            {org.farms.map((f) => (
              <li key={f.id}>
                <p className="text-sm font-semibold text-navy">
                  {f.name}
                  {f.country ? <span className="ml-1 font-normal text-muted">· {f.country}</span> : null}
                  {f.archived ? <span className="ml-2 text-xs text-watch">archived</span> : null}
                </p>
                <p className="text-xs text-secondary">{f.houses.map((h) => h.name).join(', ') || 'No houses'}</p>
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Recent alerts">
          {org.recent_alerts.length === 0 ? <p className="text-sm text-muted">No alerts yet.</p> : null}
          <ul className="divide-y divide-hairline">
            {org.recent_alerts.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                <span className="min-w-0">
                  <StatusBadge status={a.status} score={a.score} size="sm" />
                  <span className="block truncate text-xs text-muted">{houseName[a.house_id] || a.house_id}</span>
                </span>
                <span className="shrink-0 text-right text-xs text-secondary">
                  {a.resolved ? 'Resolved' : a.acknowledged ? 'Acknowledged' : 'Open'}
                  <span className="block text-muted">{timeAgo(a.created_at)}</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title="Recent AI agent runs">
        {org.recent_agent_runs.length === 0 ? (
          <p className="text-sm text-muted">The agent hasn't run for this org yet.</p>
        ) : null}
        <ul className="divide-y divide-hairline">
          {org.recent_agent_runs.map((r) => (
            <li key={r.id} className="py-2.5">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="rounded bg-ai/10 px-1.5 py-0.5 font-bold text-ai">{r.skill || 'unknown skill'}</span>
                <span className={r.status === 'completed' ? 'font-semibold text-normal' : 'font-semibold text-warning'}>
                  {r.status}
                </span>
                {r.priority ? <span className="text-secondary">priority {r.priority}</span> : null}
                <span className="text-muted">{dateTime(r.created_at)}</span>
              </div>
              {r.evidence_summary || r.error_summary ? (
                <p className="mt-1 line-clamp-2 text-sm text-secondary">{r.evidence_summary || r.error_summary}</p>
              ) : null}
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Admin actions on this org">
        {org.audit_log.length === 0 ? <p className="text-sm text-muted">No admin has changed this org.</p> : null}
        <ul className="divide-y divide-hairline">
          {org.audit_log.map((e) => (
            <li key={e.id} className="py-2 text-sm">
              <span className="font-semibold text-navy">{e.action}</span>
              <span className="text-secondary"> by {e.admin_email}</span>
              <span className="text-muted"> · {dateTime(e.created_at)}</span>
              <p className="text-xs text-secondary">“{e.reason}”</p>
            </li>
          ))}
        </ul>
      </Card>

      {dialog?.kind === 'plan' ? (
        <ReasonDialog
          title="Change plan (no payment)"
          description="Switches the plan right away and charges nothing - for comps, pilots and Enterprise deals. To have them pay, use Offer upgrade instead."
          confirmLabel="Save plan"
          onConfirm={submitPlan}
          onClose={() => setDialog(null)}
        >
          <PlanOverrideFields form={planForm} setForm={setPlanForm} />
        </ReasonDialog>
      ) : null}
      {dialog?.kind === 'offer' ? (
        <UpgradeOfferDialog
          org={org}
          onClose={() => setDialog(null)}
          onSent={() => {
            setDialog(null)
            reload()
          }}
        />
      ) : null}
      {dialog?.kind === 'suspend' ? (
        <ReasonDialog
          danger
          title="Suspend organization"
          description={`Disables sign-in for all ${org.members_active} active member(s) and revokes their sessions. Current sessions can last up to an hour.`}
          confirmLabel="Suspend"
          onConfirm={async (reason) => {
            await api.admin.suspendOrg(orgId, reason)
            reload()
          }}
          onClose={() => setDialog(null)}
        />
      ) : null}
      {dialog?.kind === 'reactivate' ? (
        <ReasonDialog
          title="Reactivate organization"
          description="Re-enables sign-in for every active member."
          confirmLabel="Reactivate"
          onConfirm={async (reason) => {
            await api.admin.reactivateOrg(orgId, reason)
            reload()
          }}
          onClose={() => setDialog(null)}
        />
      ) : null}
      {dialog?.kind === 'disable' || dialog?.kind === 'enable' ? (
        <ReasonDialog
          danger={dialog.kind === 'disable'}
          title={`${dialog.kind === 'disable' ? 'Disable' : 'Enable'} ${dialog.member.email}`}
          confirmLabel={dialog.kind === 'disable' ? 'Disable login' : 'Enable login'}
          onConfirm={async (reason) => {
            const call = dialog.kind === 'disable' ? api.admin.disableUser : api.admin.enableUser
            await call(dialog.member.id, reason)
            reload()
          }}
          onClose={() => setDialog(null)}
        />
      ) : null}
    </div>
  )
}

const OFFER_STATUS = {
  open: { label: 'Waiting for them', className: 'border-warning/30 bg-warning/5' },
  accepted: { label: 'Accepted - they upgraded', className: 'border-normal/30 bg-normal/5' },
  dismissed: { label: 'They dismissed it', className: 'border-hairline bg-surface' },
  withdrawn: { label: 'Withdrawn', className: 'border-hairline bg-surface' },
}

function OfferStatus({ org, onWithdrawn }) {
  const offer = org.upgrade_offer
  const [isWithdrawing, setIsWithdrawing] = useState(false)
  if (!offer) return null
  const meta = OFFER_STATUS[offer.status] || OFFER_STATUS.open

  async function withdraw() {
    setIsWithdrawing(true)
    try {
      await api.admin.withdrawUpgradeOffer(org.org_id)
      onWithdrawn()
    } finally {
      setIsWithdrawing(false)
    }
  }

  return (
    <div className={`flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm ${meta.className}`}>
      <p className="text-secondary">
        <Rocket size={13} className="mr-1 inline text-forest" />
        Offered <PlanBadge plan={offer.plan} /> by <b>{offer.offered_by}</b> {timeAgo(offer.offered_at)}
        {offer.email_sent ? ' · emailed' : ' · banner only (email not sent)'} · <b>{meta.label}</b>
        {offer.message ? <span className="block text-xs text-muted">“{offer.message}”</span> : null}
      </p>
      {offer.status === 'open' ? (
        <button
          onClick={withdraw}
          disabled={isWithdrawing}
          className="text-xs font-bold text-secondary hover:text-critical disabled:opacity-50"
        >
          {isWithdrawing ? 'Withdrawing...' : 'Withdraw'}
        </button>
      ) : null}
    </div>
  )
}

function BackLink() {
  return (
    <Link
      to="/admin/orgs"
      className="inline-flex items-center gap-1 text-sm font-semibold text-secondary hover:text-navy"
    >
      <ArrowLeft size={14} />
      Organizations
    </Link>
  )
}
