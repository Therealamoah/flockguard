import { useEffect, useState } from 'react'
import { Users, Crown, Clock3, Plus, X, Loader2, Shield, Wrench } from 'lucide-react'
import { useAuthStore } from '../store/useAuthStore'
import { useAppStore } from '../store/useAppStore'
import { api } from '../lib/api'
import { initialsFor } from '../lib/format'
import { timeAgo } from '../lib/time'

const ROLE_META = {
  owner: { label: 'Owner', Icon: Crown, color: '#1B4332' },
  manager: { label: 'Manager', Icon: Shield, color: '#6C63D6' },
  worker: { label: 'Worker', Icon: Wrench, color: '#B3811A' },
}

function RoleBadge({ role }) {
  const meta = ROLE_META[role] || ROLE_META.worker
  const Icon = meta.Icon
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-bold"
      style={{ color: meta.color, backgroundColor: `${meta.color}1A` }}
    >
      <Icon size={11} />
      {meta.label}
    </span>
  )
}

export default function TeamPage() {
  const { user } = useAuthStore()
  const { farms } = useAppStore()
  const [members, setMembers] = useState([])
  const [pending, setPending] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  const [showInvite, setShowInvite] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('worker')
  const [isInviting, setIsInviting] = useState(false)
  const [inviteError, setInviteError] = useState('')
  const [inviteResult, setInviteResult] = useState(null)

  const myMembership = members.find((m) => m.id === user?.uid)
  const isOwner = myMembership?.role === 'owner'

  async function load() {
    setIsLoading(true)
    setError('')
    try {
      const data = await api.team.get()
      setMembers(data.members)
      setPending(data.pending_invitations)
    } catch {
      setError('Could not load your team. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function handleInvite(e) {
    e.preventDefault()
    setInviteError('')
    setIsInviting(true)
    try {
      const sentEmail = inviteEmail.trim()
      const invitation = await api.team.invite(sentEmail, inviteRole)
      setInviteEmail('')
      setInviteRole('worker')
      setInviteResult({ email: sentEmail, emailSent: Boolean(invitation?.email_sent) })
      load()
    } catch (err) {
      if (err.status === 409) {
        setInviteError('That person is already on the team or already invited.')
      } else if (err.status === 402) {
        setInviteError(err.detail || 'Your plan has reached its team seat limit.')
      } else {
        setInviteError('Could not send this invitation.')
      }
    } finally {
      setIsInviting(false)
    }
  }

  async function handleRoleChange(memberId, role) {
    try {
      await api.team.updateRole(memberId, role)
      setMembers((prev) => prev.map((m) => (m.id === memberId ? { ...m, role } : m)))
    } catch {
      setError('Could not change this role.')
    }
  }

  async function handleRemove(memberId) {
    if (!window.confirm('Remove this person from your team? They will lose access immediately.')) return
    try {
      await api.team.removeMember(memberId)
      setMembers((prev) => prev.filter((m) => m.id !== memberId))
    } catch {
      setError('Could not remove this member.')
    }
  }

  async function handleCancelInvitation(invitationId) {
    try {
      await api.team.cancelInvitation(invitationId)
      setPending((prev) => prev.filter((i) => i.id !== invitationId))
    } catch {
      setError('Could not cancel this invitation.')
    }
  }

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
            <Users size={20} />
          </span>
          <div>
            <h1 className="font-display text-2xl font-extrabold text-navy">Team</h1>
            <p className="text-sm text-secondary">Who has access to {farms[0]?.name || 'your farm'}.</p>
          </div>
        </div>
        {isOwner ? (
          <button
            onClick={() => {
              setShowInvite((v) => !v)
              setInviteResult(null)
              setInviteError('')
            }}
            className="flex items-center gap-1.5 rounded-lg bg-forest px-4 py-2 text-sm font-bold text-white hover:bg-forest-dark"
          >
            <Plus size={15} />
            Invite Member
          </button>
        ) : null}
      </div>

      {showInvite ? (
        <form onSubmit={handleInvite} className="mt-4 rounded-xl border border-hairline bg-surface p-4 shadow-sm">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex-1">
              <label className="mb-1 block text-xs font-semibold text-secondary">Email</label>
              <input
                required
                type="email"
                value={inviteEmail}
                onChange={(e) => {
                  setInviteEmail(e.target.value)
                  setInviteResult(null)
                }}
                placeholder="teammate@example.com"
                className="w-full rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-semibold text-secondary">Role</label>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className="rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest"
              >
                <option value="worker">Worker</option>
                <option value="manager">Manager</option>
              </select>
            </div>
            <button
              type="submit"
              disabled={isInviting}
              className="rounded-lg bg-forest px-4 py-2 text-sm font-bold text-white hover:bg-forest-dark disabled:opacity-60"
            >
              {isInviting ? 'Sending...' : 'Send Invitation'}
            </button>
            <button
              type="button"
              onClick={() => setShowInvite(false)}
              className="rounded-lg p-2 text-muted hover:text-navy"
            >
              <X size={16} />
            </button>
          </div>
          {inviteError ? <p className="mt-2 text-sm text-critical">{inviteError}</p> : null}
          {inviteResult ? (
            inviteResult.emailSent ? (
              <p className="mt-2 text-xs font-medium text-normal">
                ✓ Invite email sent to {inviteResult.email}.
              </p>
            ) : (
              <p className="mt-2 text-xs text-muted">
                Invitation created, but email delivery isn't configured - share this invite with{' '}
                {inviteResult.email} directly (they'll see it once they sign in with this email address).
              </p>
            )
          ) : (
            <p className="mt-2 text-xs text-muted">
              They'll get an email invite; if delivery isn't set up, they can still sign in directly with this email
              address to accept it.
            </p>
          )}
        </form>
      ) : null}

      {error ? <p className="mt-4 text-sm text-critical">{error}</p> : null}

      {isLoading ? (
        <div className="mt-6 flex items-center justify-center gap-2 py-16 text-sm text-secondary">
          <Loader2 size={16} className="animate-spin" />
          Loading team...
        </div>
      ) : (
        <div className="mt-4 space-y-2">
          {members.map((member) => (
            <div
              key={member.id}
              className="flex flex-wrap items-center gap-3 rounded-xl border border-hairline bg-surface p-4 shadow-sm"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-forest text-xs font-bold text-white">
                {initialsFor({ displayName: member.display_name, email: member.email })}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-navy">
                  {member.display_name || member.email}
                  {member.id === user?.uid ? <span className="ml-1.5 text-xs text-muted">(you)</span> : null}
                </p>
                <p className="truncate text-xs text-secondary">{member.email}</p>
              </div>

              {isOwner && member.id !== user?.uid ? (
                <select
                  value={member.role}
                  onChange={(e) => handleRoleChange(member.id, e.target.value)}
                  className="rounded-lg border border-hairline px-2 py-1.5 text-xs font-semibold outline-none focus:border-forest"
                >
                  <option value="worker">Worker</option>
                  <option value="manager">Manager</option>
                  <option value="owner">Owner</option>
                </select>
              ) : (
                <RoleBadge role={member.role} />
              )}

              {isOwner && member.id !== user?.uid ? (
                <button
                  onClick={() => handleRemove(member.id)}
                  className="rounded-lg px-2 py-1.5 text-xs font-semibold text-critical hover:bg-critical/5"
                >
                  Remove
                </button>
              ) : null}
            </div>
          ))}
        </div>
      )}

      {pending.length > 0 ? (
        <div className="mt-8">
          <h2 className="text-sm font-bold uppercase tracking-wide text-secondary">Pending Invitations</h2>
          <div className="mt-3 space-y-2">
            {pending.map((invitation) => (
              <div
                key={invitation.id}
                className="flex items-center gap-3 rounded-xl border border-dashed border-hairline bg-surface/50 p-4"
              >
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-bg text-muted">
                  <Clock3 size={15} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-navy">{invitation.email}</p>
                  <p className="text-xs text-secondary">
                    Invited {timeAgo(invitation.created_at)} · expires {new Date(invitation.expires_at).toLocaleDateString()}
                  </p>
                </div>
                <RoleBadge role={invitation.role} />
                <span className="rounded-full bg-hairline/70 px-2 py-1 text-xs font-semibold text-secondary">Pending</span>
                {isOwner ? (
                  <button
                    onClick={() => handleCancelInvitation(invitation.id)}
                    className="rounded-lg px-2 py-1.5 text-xs font-semibold text-critical hover:bg-critical/5"
                  >
                    Cancel
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
