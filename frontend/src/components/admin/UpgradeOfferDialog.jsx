import { useState } from 'react'
import { Send, X } from 'lucide-react'
import { api } from '../../lib/api'
import { ghs } from '../../lib/adminFormat'

// Must match backend PLAN_CATALOG (app/services/billing_service.py).
const PAID_PLANS = [
  { plan: 'starter', label: 'Starter', price: 249, houses: 10 },
  { plan: 'growth', label: 'Growth', price: 549, houses: 25 },
  { plan: 'pro', label: 'Pro', price: 1199, houses: 60 },
]
const RANK = { pilot: 0, starter: 1, growth: 2, pro: 3, enterprise: 4 }

// "Offer upgrade": the farmer gets an email + in-app banner and upgrades
// (and pays through Paystack) themselves. Nothing changes until they do.
export default function UpgradeOfferDialog({ org, onClose, onSent }) {
  const options = PAID_PLANS.filter((p) => RANK[p.plan] > (RANK[org.plan] ?? 0))
  const [plan, setPlan] = useState(options[0]?.plan)
  const [message, setMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setIsSending(true)
    setError('')
    try {
      const result = await api.admin.offerUpgrade(org.org_id, { plan, message: message.trim() || null })
      onSent(result)
    } catch (err) {
      setError(err.detail || 'Could not send the offer.')
      setIsSending(false)
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <form onSubmit={handleSubmit} className="relative w-full max-w-md rounded-xl border border-hairline bg-surface p-5 shadow-xl">
        <div className="flex items-start justify-between gap-3">
          <h2 className="font-display text-lg font-extrabold text-navy">Offer an upgrade</h2>
          <button type="button" onClick={onClose} className="text-muted hover:text-navy" aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <p className="mt-1 text-sm text-secondary">
          {org.owner_email ? (
            <>
              <b>{org.owner_email}</b> gets an email and a banner in the app.
            </>
          ) : (
            'The owner sees a banner in the app (no owner email on file, so no email).'
          )}{' '}
          They upgrade and pay by card themselves - their plan doesn't change until they do.
        </p>

        {options.length === 0 ? (
          <p className="mt-4 rounded-lg bg-bg p-3 text-sm text-secondary">
            They're already on the top self-serve plan. Use Change plan for an Enterprise deal.
          </p>
        ) : (
          <>
            <div className="mt-4 grid gap-2">
              {options.map((p) => (
                <label
                  key={p.plan}
                  className={`flex cursor-pointer items-center justify-between rounded-lg border px-3 py-2.5 text-sm ${
                    plan === p.plan ? 'border-forest bg-forest/5' : 'border-hairline'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <input type="radio" name="plan" checked={plan === p.plan} onChange={() => setPlan(p.plan)} />
                    <b className="text-navy">{p.label}</b>
                    <span className="text-xs text-muted">{p.houses} houses</span>
                  </span>
                  <span className="font-semibold text-navy">{ghs(p.price)}/mo</span>
                </label>
              ))}
            </div>
            <label className="mt-4 block text-xs font-semibold text-secondary">
              Personal note (optional - shown in the email and banner)
              <textarea
                rows={3}
                maxLength={1000}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="e.g. You're at 9 of 10 houses - Growth gives you room for the new site."
                className="mt-1 w-full rounded-lg border border-hairline bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-forest"
              />
            </label>
          </>
        )}

        {error ? <p className="mt-2 text-sm text-critical">{error}</p> : null}
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-sm font-semibold text-secondary hover:text-navy">
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSending || options.length === 0}
            className="flex items-center gap-1.5 rounded-lg bg-forest px-4 py-2 text-sm font-bold text-white hover:bg-forest-dark disabled:opacity-60"
          >
            <Send size={14} />
            {isSending ? 'Sending...' : 'Send offer'}
          </button>
        </div>
      </form>
    </div>
  )
}
