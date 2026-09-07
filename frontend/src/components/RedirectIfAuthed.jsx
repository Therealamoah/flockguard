import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../store/useAuthStore'

export default function RedirectIfAuthed() {
  const { user, isLoading } = useAuthStore()

  if (isLoading) return null
  if (user) return <Navigate to="/" replace />

  return <Outlet />
}
