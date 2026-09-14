import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Mail, CheckCircle2, Warehouse, Loader2 } from 'lucide-react'
import { api } from '../lib/api'
import { useAppStore } from '../store/useAppStore'
import { forceRefreshToken } from '../lib/firebase'

const ROLE_LABEL = { owner: 'Owner', manager: 'Manager', worker: 'Worker' }

export default function InvitationsPage() {
  const { pendingInvitations } = useAppStore()
  const [acceptingId, setAcceptingId] = useState(null)
  const [error, setError] = useState('')
  const navigate = useNavigate()

  async function handleAccept(invitation) {
    setError('')
    setAcceptingId(invitation.id)
    try {
      await api.team.acceptInvitation(invitation.org_id, invitation.id)
      // The org_id custom claim was just set server-side - it only shows
      // up on a freshly minted token, so force one before re-bootstrapping.
      await forceRefreshToken()
      await useAppStore.getState().bootstrap()
      navigate('/overview', { replace: true })
    } catch {
      setError('Could not accept this invitation. It may have expired or already been used.')
      setAcceptingId(null)
    }
  }

  return (
    <div className="min-h-screen bg-bg">
      <div className="mx-auto max-w-xl px-4 py-16">
        <div className="rounded-2xl border border-hairline bg-surface p-8 shadow-sm">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
              <Mail size={20} />
            </span>
            <h1 className="font-display text-2xl font-extrabold text-navy">You've been invited</h1>
          </div>
          <p className="mt-2 text-sm text-secondary">
            {pendingInvitations.length > 1
              ? "Someone has invited you to join their farm's team on FlockGuard."
              : "Accept below to join the team, or create your own farm instead."}
          </p>

          <div className="mt-6 space-y-3">
            {pendingInvitations.map((invitation) => (
              <div key={invitation.id} className="flex items-center gap-3 rounded-xl border border-hairline p-4">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
                  <Warehouse size={18} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-navy">
                    Invited by {invitation.invited_by_email || 'a farm owner'}
                  </p>
                  <p className="text-xs text-secondary">
                    Role: {ROLE_LABEL[invitation.role] || invitation.role}
                  </p>
                </div>
                <button
                  onClick={() => handleAccept(invitation)}
                  disabled={acceptingId === invitation.id}
                  className="flex shrink-0 items-center gap-1.5 rounded-lg bg-forest px-4 py-2 text-sm font-bold text-white hover:bg-forest-dark disabled:opacity-60"
                >
                  {acceptingId === invitation.id ? (
                    <Loader2 size={15} className="animate-spin" />
                  ) : (
                    <CheckCircle2 size={15} />
                  )}
                  Accept
                </button>
              </div>
            ))}
          </div>

          {error ? <p className="mt-4 text-sm text-critical">{error}</p> : null}

          <button
            onClick={() => navigate('/onboarding')}
            className="mt-6 text-sm font-semibold text-secondary hover:text-navy"
          >
            Set up my own farm instead →
          </button>
        </div>
      </div>
    </div>
  )
}
