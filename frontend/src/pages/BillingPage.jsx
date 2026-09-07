import { CreditCard, Sparkles } from 'lucide-react'

export default function BillingPage() {
  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
          <CreditCard size={20} />
        </span>
        <div>
          <h1 className="font-display text-2xl font-extrabold text-navy">Billing</h1>
          <p className="text-sm text-navy/60">Your plan and usage.</p>
        </div>
      </div>

      <div className="mt-6 overflow-hidden rounded-xl border border-hairline bg-surface shadow-sm">
        <div className="bg-linear-to-br from-forest to-forest-dark p-5 text-white">
          <span className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-white/70">
            <Sparkles size={13} />
            Current plan
          </span>
          <p className="mt-1 font-display text-xl font-extrabold">Free tier</p>
        </div>
        <p className="p-5 text-sm text-navy/60">
          FlockGuard is in active development — billing and paid plans aren't live yet.
        </p>
      </div>
    </div>
  )
}
