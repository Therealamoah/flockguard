import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Rocket, X } from 'lucide-react'
import { api } from '../lib/api'

// Shown to an org's owner when FlockGuard has suggested a plan for them
// (admin console → Offer upgrade). Everyone else gets a 403 from the
// endpoint, which just means "no banner". Billing shows its own version.
export default function UpgradeOfferBanner() {
  const { pathname } = useLocation()
  const [offer, setOffer] = useState(null)

  useEffect(() => {
    let cancelled = false
    api.billing
      .upgradeOffer()
      .then(({ offer: next }) => {
        if (!cancelled) setOffer(next)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  if (!offer || pathname.startsWith('/billing')) return null

  async function dismiss() {
    setOffer(null)
    api.billing.dismissUpgradeOffer().catch(() => {})
  }

  const label = offer.plan.charAt(0).toUpperCase() + offer.plan.slice(1)
  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-forest/20 bg-forest/5 px-4 py-2.5 text-sm lg:px-6">
      <Rocket size={16} className="shrink-0 text-forest" />
      <p className="min-w-0 flex-1 text-navy">
        <b>We recommend the {label} plan for your farm</b>
        {offer.message ? <span className="text-secondary"> - {offer.message}</span> : null}
      </p>
      <Link
        to={`/billing?offer=${offer.plan}`}
        className="rounded-lg bg-forest px-3 py-1.5 text-xs font-bold text-white hover:bg-forest-dark"
      >
        See {label}
      </Link>
      <button onClick={dismiss} className="text-muted hover:text-navy" aria-label="Dismiss">
        <X size={16} />
      </button>
    </div>
  )
}
