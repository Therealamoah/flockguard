import { useEffect } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/useAuthStore'
import { useAppStore } from '../store/useAppStore'
import LoadingScreen from './LoadingScreen'

export default function RequireAuth() {
  const { user, isLoading } = useAuthStore()
  const { isBootstrapped, needsOnboarding, pendingInvitations, bootstrap } = useAppStore()
  const location = useLocation()

  useEffect(() => {
    if (user && !isBootstrapped) bootstrap()
  }, [user, isBootstrapped, bootstrap])

  if (isLoading) {
    return <LoadingScreen label="Loading FlockGuard..." />
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (!isBootstrapped) {
    return <LoadingScreen label="Loading your farm..." />
  }

  if (needsOnboarding && pendingInvitations.length > 0 && location.pathname !== '/invitations') {
    // Someone invited onto an existing farm shouldn't be forced through
    // farm creation - let them accept first.
    return <Navigate to="/invitations" replace />
  }

  if (needsOnboarding && pendingInvitations.length === 0 && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />
  }

  return <Outlet />
}
