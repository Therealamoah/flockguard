import { useEffect, useState } from 'react'
import {
  CreditCard,
  Sparkles,
  Warehouse,
  Bird,
  Users,
  Loader2,
  Lock,
  Sparkle,
  HardDrive,
  Check,
  Mail,
  AlertTriangle,
  Briefcase,
  X,
  Rocket,
} from 'lucide-react'
import { api } from '../lib/api'

const METRIC_META = {
  houses: { label: 'Houses', Icon: Warehouse },
  birds: { label: 'Active Birds', Icon: Bird },
  team_members: { label: 'Team Members', Icon: Users },
}

const PLAN_LABEL = { pilot: 'Pilot', starter: 'Starter', growth: 'Growth', pro: 'Pro', enterprise: 'Enterprise' }

function UsageBar({ label, Icon, used, limit }) {
  const pct = limit ? Math.min(100, Math.round((used / limit) * 100)) : 0
  const nearLimit = limit && used / limit >= 0.8
  return (
    <div className="rounded-xl border border-hairline bg-surface p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-1.5 text-xs font-semibold text-secondary">
          <Icon size={13} />
          {label}
        </span>
        <span className="text-sm font-bold text-navy">
          {used} / {limit ?? '—'}
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-hairline">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: nearLimit ? '#C05A1D' : '#2F9E58' }}
        />
      </div>
    </div>
  )
}

function PlanCard({ plan, isCurrent, onUpgrade, isCheckingOut, enterpriseRequest, onRequestEnterprise, isRecommended }) {
  const isEnterprise = plan.plan === 'enterprise'
  return (
    <div
      className={[
        'flex flex-col rounded-xl border bg-surface p-4 shadow-sm',
        isCurrent || isRecommended ? 'border-forest ring-1 ring-forest/30' : 'border-hairline',
      ].join(' ')}
    >
      {isRecommended && !isCurrent ? (
        <span className="mb-2 flex w-fit items-center gap-1 rounded-full bg-forest px-2.5 py-0.5 text-[11px] font-bold text-white">
          <Rocket size={11} />
          Recommended for you
        </span>
      ) : null}
      <div className="flex items-center justify-between">
        <span className="text-sm font-bold uppercase text-navy">{PLAN_LABEL[plan.plan]}</span>
        {isCurrent ? (
          <span className="flex items-center gap-1 rounded-full bg-forest/10 px-2.5 py-1 text-xs font-semibold text-forest">
            <Check size={12} />
            Current
          </span>
        ) : null}
      </div>
      <p className="mt-1 font-display text-lg font-extrabold text-navy">
        {isEnterprise ? 'Custom' : `GHS ${plan.price_ghs}`}
        {!isEnterprise ? <span className="text-xs font-medium text-muted"> /month</span> : null}
      </p>
      {plan.limits ? (
        <ul className="mt-2 space-y-0.5 text-xs text-secondary">
          <li>{plan.limits.houses} houses</li>
          <li>{plan.limits.birds.toLocaleString()} birds</li>
          <li>{plan.limits.team_members} team members</li>
          <li>{plan.limits.ai_requests_monthly.toLocaleString()} AI requests/mo</li>
        </ul>
      ) : (
        <p className="mt-2 text-xs text-secondary">Unlimited/custom limits, tailored to your operation.</p>
      )}
      <div className="mt-3">
        {isCurrent ? null : isEnterprise ? (
          enterpriseRequest ? (
            <p className="flex items-center justify-center gap-1.5 rounded-lg bg-forest/10 px-3 py-2 text-xs font-bold text-forest">
              <Check size={13} />
              Request received - we'll be in touch
            </p>
          ) : (
            <button
              onClick={onRequestEnterprise}
              className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-hairline px-3 py-2 text-xs font-bold text-navy hover:bg-forest/5"
            >
              <Mail size={13} />
              Request Enterprise
            </button>
          )
        ) : (
          <button
            onClick={() => onUpgrade(plan.plan)}
            disabled={isCheckingOut}
            className="w-full rounded-lg bg-forest px-3 py-2 text-xs font-bold text-white hover:bg-forest-dark disabled:opacity-60"
          >
            {isCheckingOut ? 'Redirecting...' : 'Upgrade'}
          </button>
        )}
      </div>
    </div>
  )
}

const CONTACT_OPTIONS = [
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'call', label: 'Phone call' },
  { value: 'email', label: 'Email' },
]

const inputClass =
  'w-full rounded-lg border border-hairline bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-forest'

// Replaces the old mailto: link - saved server-side so the request shows up
// in the admin console's Enterprise page (backend/app/services/enterprise_service.py).
function EnterpriseRequestDialog({ usage, onClose, onSent }) {
  const [form, setForm] = useState({ houses: '', birds: '', phone: '', contact_method: 'whatsapp', message: '' })
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState('')
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })
  const needsPhone = form.contact_method !== 'email' && !form.phone.trim()

  async function handleSubmit(e) {
    e.preventDefault()
    setIsSending(true)
    setError('')
    try {
      const { request } = await api.billing.requestEnterprise({
        houses: form.houses === '' ? null : Number(form.houses),
        birds: form.birds === '' ? null : Number(form.birds),
        phone: form.phone.trim() || null,
        contact_method: form.contact_method,
        message: form.message.trim() || null,
      })
      onSent(request)
    } catch (err) {
      setError(err.detail || 'Could not send your request. Please try again.')
      setIsSending(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <form
        onSubmit={handleSubmit}
        className="relative max-h-[90vh] w-full max-w-md overflow-y-auto rounded-xl border border-hairline bg-surface p-5 shadow-xl"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <Briefcase size={18} className="text-forest" />
            <h2 className="font-display text-lg font-extrabold text-navy">Request Enterprise</h2>
          </div>
          <button type="button" onClick={onClose} className="text-muted hover:text-navy" aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <p className="mt-1 text-sm text-secondary">
          Tell us about your operation and our team will contact you with a custom plan.
        </p>

        <div className="mt-4 grid grid-cols-2 gap-3">
          <label className="text-xs font-semibold text-secondary">
            Houses you need
            <input
              type="number"
              min={0}
              value={form.houses}
              onChange={set('houses')}
              placeholder={`now ${usage?.houses?.used ?? 0}`}
              className={`mt-1 ${inputClass}`}
            />
          </label>
          <label className="text-xs font-semibold text-secondary">
            Birds you need
            <input
              type="number"
              min={0}
              value={form.birds}
              onChange={set('birds')}
              placeholder={`now ${(usage?.birds?.used ?? 0).toLocaleString()}`}
              className={`mt-1 ${inputClass}`}
            />
          </label>
        </div>

        <label className="mt-3 block text-xs font-semibold text-secondary">
          Phone number
          <input
            type="tel"
            value={form.phone}
            onChange={set('phone')}
            maxLength={40}
            placeholder="+233..."
            className={`mt-1 ${inputClass}`}
          />
        </label>

        <p className="mt-3 text-xs font-semibold text-secondary">Best way to reach you</p>
        <div className="mt-1 flex flex-wrap gap-2">
          {CONTACT_OPTIONS.map((o) => (
            <button
              key={o.value}
              type="button"
              onClick={() => setForm({ ...form, contact_method: o.value })}
              className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                form.contact_method === o.value
                  ? 'border-forest bg-forest text-white'
                  : 'border-hairline text-secondary hover:border-forest'
              }`}
            >
              {o.label}
            </button>
          ))}
        </div>

        <label className="mt-3 block text-xs font-semibold text-secondary">
          Anything else? (optional)
          <textarea
            rows={3}
            value={form.message}
            onChange={set('message')}
            maxLength={2000}
            placeholder="Number of sites, what you need most..."
            className={`mt-1 ${inputClass}`}
          />
        </label>

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
            disabled={isSending || needsPhone}
            className="rounded-lg bg-forest px-4 py-2 text-sm font-bold text-white hover:bg-forest-dark disabled:opacity-60"
          >
            {isSending ? 'Sending...' : 'Send request'}
          </button>
        </div>
        {needsPhone ? (
          <p className="mt-2 text-right text-xs text-muted">Add a phone number for a call or WhatsApp.</p>
        ) : null}
      </form>
    </div>
  )
}

export default function BillingPage() {
  const [billing, setBilling] = useState(null)
  const [usage, setUsage] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [forbidden, setForbidden] = useState(false)
  const [checkoutPlan, setCheckoutPlan] = useState(null)
  const [isCancelling, setIsCancelling] = useState(false)
  const [banner, setBanner] = useState(null)
  const [enterpriseRequest, setEnterpriseRequest] = useState(null)
  const [showEnterpriseForm, setShowEnterpriseForm] = useState(false)
  const [upgradeOffer, setUpgradeOffer] = useState(null)

  async function load() {
    const [billingData, usageData, enterpriseData, offerData] = await Promise.all([
      api.billing.get(),
      api.billing.usage(),
      api.billing.enterpriseRequest().catch(() => ({ request: null })),
      api.billing.upgradeOffer().catch(() => ({ offer: null })),
    ])
    setBilling(billingData)
    setUsage(usageData)
    setEnterpriseRequest(enterpriseData.request)
    setUpgradeOffer(offerData.offer)
  }

  // Read once at mount, outside the effect: React 18 StrictMode
  // double-invokes effects in dev, and history.replaceState below is
  // destructive - re-reading window.location.search fresh on the second
  // invocation would find the reference already stripped by the first,
  // silently skipping verification. Capturing it in state up front (a
  // lazy initializer runs on render, before either effect invocation)
  // decouples "what reference to verify" from "clearing the URL bar",
  // so the effect stays safe to run more than once.
  const [pendingReference] = useState(() => new URLSearchParams(window.location.search).get('reference'))

  useEffect(() => {
    let cancelled = false

    async function init() {
      try {
        if (pendingReference) {
          window.history.replaceState({}, '', window.location.pathname)
          try {
            await api.billing.verify(pendingReference)
            if (!cancelled) setBanner({ type: 'success', text: 'Payment confirmed - your plan is now active.' })
          } catch (err) {
            if (!cancelled) setBanner({ type: 'error', text: err.detail || 'Could not confirm that payment.' })
          }
        }
        await load()
      } catch (err) {
        if (err.status === 403) setForbidden(true)
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    init()
    return () => {
      cancelled = true
    }
  }, [pendingReference])

  async function handleUpgrade(plan) {
    setCheckoutPlan(plan)
    setBanner(null)
    try {
      const { authorization_url } = await api.billing.checkout(plan)
      window.location.href = authorization_url
    } catch (err) {
      setBanner({ type: 'error', text: err.detail || 'Could not start checkout.' })
      setCheckoutPlan(null)
    }
  }

  async function handleCancel() {
    if (!window.confirm("Cancel your subscription? You'll drop back to the free Pilot plan and its limits.")) return
    setIsCancelling(true)
    try {
      await api.billing.cancel()
      setBanner({ type: 'success', text: "Subscription cancelled - you're back on the free Pilot plan." })
      await load()
    } catch (err) {
      setBanner({ type: 'error', text: err.detail || 'Could not cancel this subscription.' })
    } finally {
      setIsCancelling(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center gap-2 p-6 text-sm text-secondary">
        <Loader2 size={16} className="animate-spin" />
        Loading billing...
      </div>
    )
  }

  if (forbidden) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <div className="flex flex-col items-center gap-2 rounded-xl border border-hairline bg-surface py-16 text-center shadow-sm">
          <Lock size={28} className="text-muted" />
          <p className="text-sm font-semibold text-navy">Only the farm owner can view billing.</p>
          <p className="text-sm text-secondary">Ask your organization's owner for plan and usage details.</p>
        </div>
      </div>
    )
  }

  const subscription = billing?.subscription
  const currentPlan = subscription?.plan || 'pilot'

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
          <CreditCard size={20} />
        </span>
        <div>
          <h1 className="font-display text-2xl font-extrabold text-navy">Billing</h1>
          <p className="text-sm text-secondary">Your plan and usage.</p>
        </div>
      </div>

      {banner ? (
        <div
          className={[
            'mt-4 flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-medium',
            banner.type === 'success' ? 'bg-normal/10 text-normal' : 'bg-critical/10 text-critical',
          ].join(' ')}
        >
          {banner.type === 'error' ? <AlertTriangle size={15} className="shrink-0" /> : <Check size={15} className="shrink-0" />}
          {banner.text}
        </div>
      ) : null}

      <div className="mt-4 overflow-hidden rounded-xl border border-hairline bg-surface shadow-sm">
        <div className="bg-linear-to-br from-forest to-forest-dark p-5 text-white">
          <span className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-white/70">
            <Sparkles size={13} />
            Current plan
          </span>
          <p className="mt-1 font-display text-xl font-extrabold uppercase">{currentPlan}</p>
          <p className="mt-1 text-sm text-white/70">
            {subscription?.currency} {subscription?.price_ghs ?? 0} / month · Status: {subscription?.status}
          </p>
        </div>
        <div className="flex items-center justify-between gap-3 p-5">
          <p className="text-sm text-secondary">
            {billing?.note || (currentPlan !== 'pilot' ? 'Billed monthly via Paystack.' : null)}
          </p>
          {currentPlan !== 'pilot' ? (
            <button
              onClick={handleCancel}
              disabled={isCancelling}
              className="shrink-0 rounded-lg border border-hairline px-3 py-1.5 text-xs font-bold text-critical hover:bg-critical/5 disabled:opacity-60"
            >
              {isCancelling ? 'Cancelling...' : 'Cancel Plan'}
            </button>
          ) : null}
        </div>
      </div>

      {upgradeOffer ? (
        <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-forest/30 bg-forest/5 p-4">
          <Rocket size={20} className="shrink-0 text-forest" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-bold text-navy">
              We recommend the {upgradeOffer.plan.charAt(0).toUpperCase() + upgradeOffer.plan.slice(1)} plan for
              your farm - GHS {upgradeOffer.price_ghs}/month
            </p>
            {upgradeOffer.message ? <p className="mt-0.5 text-sm text-secondary">{upgradeOffer.message}</p> : null}
          </div>
          <button
            onClick={() => handleUpgrade(upgradeOffer.plan)}
            disabled={Boolean(checkoutPlan)}
            className="rounded-lg bg-forest px-4 py-2 text-sm font-bold text-white hover:bg-forest-dark disabled:opacity-60"
          >
            {checkoutPlan === upgradeOffer.plan ? 'Redirecting...' : 'Upgrade now'}
          </button>
        </div>
      ) : null}

      <h2 className="mt-6 text-sm font-bold uppercase tracking-wide text-secondary">Usage</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        {Object.entries(METRIC_META).map(([key, meta]) => (
          <UsageBar key={key} label={meta.label} Icon={meta.Icon} used={usage?.[key]?.used ?? 0} limit={usage?.[key]?.limit} />
        ))}
        <UsageBar
          label="AI Requests"
          Icon={Sparkle}
          used={usage?.ai_requests?.used ?? 0}
          limit={usage?.ai_requests?.limit}
        />
        <div className="rounded-xl border border-hairline bg-surface p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-secondary">
              <HardDrive size={13} />
              Storage
            </span>
            <span className="text-sm font-bold text-navy">{usage?.storage?.used_mb ?? 0} MB</span>
          </div>
          <p className="mt-2 text-[11px] text-muted">Photos and voice notes attached to Flock Checks.</p>
        </div>
      </div>
      <p className="mt-3 text-xs text-muted">
        AI Requests reset at the start of each calendar month. Storage is a running total of everything ever
        uploaded.
      </p>

      <h2 className="mt-8 text-sm font-bold uppercase tracking-wide text-secondary">Plans</h2>
      <p className="mt-1 text-xs text-muted">
        Card payment only for now - subscriptions auto-renew monthly, which Paystack only supports via card.
      </p>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {billing?.plans?.map((plan) => (
          <PlanCard
            key={plan.plan}
            plan={plan}
            isCurrent={plan.plan === currentPlan}
            onUpgrade={handleUpgrade}
            isCheckingOut={checkoutPlan === plan.plan}
            enterpriseRequest={enterpriseRequest}
            onRequestEnterprise={() => setShowEnterpriseForm(true)}
            isRecommended={upgradeOffer?.plan === plan.plan}
          />
        ))}
      </div>

      {showEnterpriseForm ? (
        <EnterpriseRequestDialog
          usage={usage}
          onClose={() => setShowEnterpriseForm(false)}
          onSent={(request) => {
            setEnterpriseRequest(request)
            setShowEnterpriseForm(false)
            setBanner({ type: 'success', text: "Thanks - your Enterprise request is in. We'll contact you shortly." })
          }}
        />
      ) : null}
    </div>
  )
}
