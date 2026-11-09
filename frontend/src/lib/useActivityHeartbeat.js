import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import { api } from './api'

const INTERVAL_MS = 60_000

// Tells the backend "this person is using FlockGuard right now" - the data
// behind the admin console's Activity page (online now, DAU/WAU/MAU,
// dormant users; see backend/app/services/activity_service.py). Fires on
// load, on every page change, when the tab comes back into view, and once a
// minute while it stays visible. A hidden tab sends nothing, so a laptop
// left open overnight doesn't count as "online". Failures are ignored - this
// must never get in the way of the app itself.
export function useActivityHeartbeat(enabled = true) {
  const { pathname } = useLocation()

  useEffect(() => {
    if (!enabled) return undefined
    const beat = () => {
      if (document.visibilityState === 'visible') api.activity.heartbeat(pathname).catch(() => {})
    }
    beat()
    const id = setInterval(beat, INTERVAL_MS)
    document.addEventListener('visibilitychange', beat)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', beat)
    }
  }, [enabled, pathname])
}
