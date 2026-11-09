import { useEffect, useState } from 'react'
import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'
import { ShieldOff } from 'lucide-react'
import { useAuthStore } from '../store/useAuthStore'
import { hasPlatformAdminClaim } from '../lib/firebase'
import LoadingScreen from './LoadingScreen'

// Deliberately NOT nested inside RequireAuth: a platform admin doesn't need a
// farm of their own, so the farm bootstrap / onboarding redirect must not run.
export default function RequireAdmin() {
  const { user, isLoading } = useAuthStore()
  const [isAdmin, setIsAdmin] = useState(null)
  const location = useLocation()

  useEffect(() => {
    if (!user) return
    let cancelled = false
    hasPlatformAdminClaim(true)
      .then((ok) => !cancelled && setIsAdmin(ok))
      .catch(() => !cancelled && setIsAdmin(false))
    return () => {
      cancelled = true
    }
  }, [user])

  if (isLoading) return <LoadingScreen label="Loading FlockGuard..." />
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />
  if (isAdmin === null) return <LoadingScreen label="Checking admin access..." />

  if (!isAdmin) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-bg p-6 text-center">
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-critical/10 text-critical">
          <ShieldOff size={22} />
        </span>
        <h1 className="font-display text-xl font-extrabold text-navy">No admin access</h1>
        <p className="max-w-sm text-sm text-secondary">
          This area is for FlockGuard platform operators. If you were just granted access, sign out and back in.
        </p>
        <p className="text-xs text-muted">Signed in as {user.email}</p>
        <Link
          to="/overview"
          className="mt-2 rounded-lg bg-forest px-4 py-2 text-sm font-bold text-white hover:bg-forest-dark"
        >
          Back to my farm
        </Link>
      </div>
    )
  }

  return <Outlet />
}
