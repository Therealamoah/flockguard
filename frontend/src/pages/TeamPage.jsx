import { Users, Crown, Clock3 } from 'lucide-react'
import { useAuthStore } from '../store/useAuthStore'
import { useAppStore } from '../store/useAppStore'
import { displayName, initialsFor } from '../lib/format'

export default function TeamPage() {
  const { user } = useAuthStore()
  const { farms } = useAppStore()

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
          <Users size={20} />
        </span>
        <div>
          <h1 className="font-display text-2xl font-extrabold text-navy">Team</h1>
          <p className="text-sm text-navy/60">Who has access to {farms[0]?.name || 'your farm'}.</p>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-hairline bg-surface p-4 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-forest text-xs font-bold text-white">
            {initialsFor(user)}
          </div>
          <div className="flex-1">
            <p className="text-sm font-semibold text-navy">{displayName(user)}</p>
            <p className="text-xs text-navy/50">{user?.email}</p>
          </div>
          <span className="flex items-center gap-1 rounded-full bg-forest/10 px-2.5 py-1 text-xs font-bold text-forest">
            <Crown size={12} />
            Owner
          </span>
        </div>
      </div>

      <div className="mt-4 flex items-start gap-3 rounded-xl border border-dashed border-hairline bg-surface/50 p-4">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-bg text-navy/40">
          <Clock3 size={15} />
        </span>
        <p className="text-sm text-navy/50">
          Inviting teammates isn't wired up yet — organizations and memberships are still on the roadmap.
        </p>
      </div>
    </div>
  )
}
