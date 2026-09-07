import { useEffect } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/useAuthStore'
import { useAppStore } from '../store/useAppStore'

export default function RequireAuth() {
  const { user, isLoading } = useAuthStore()
  const { isBootstrapped, needsOnboarding, bootstrap } = useAppStore()
  const location = useLocation()

  useEffect(() => {
    if (user && !isBootstrapped) bootstrap()
  }, [user, isBootstrapped, bootstrap])

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg text-sm text-navy/60">
        Loading FlockGuard...
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (!isBootstrapped) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg text-sm text-navy/60">
        Loading your farm...
      </div>
    )
  }

  if (needsOnboarding && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />
  }

  return <Outlet />
}
