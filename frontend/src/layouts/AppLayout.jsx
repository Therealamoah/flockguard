import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  Home,
  Radar as RadarIcon,
  Bird,
  Warehouse,
  ClipboardList,
  ShieldAlert,
  BarChart3,
  Sparkles,
  Settings,
  Bell,
  Plus,
  Users,
  CreditCard,
  LogOut,
  Sun,
  Moon,
  Menu,
  X,
} from 'lucide-react'
import LogoMark from '../components/Logo'
import { useAuthStore } from '../store/useAuthStore'
import { useAppStore } from '../store/useAppStore'
import { useThemeStore } from '../store/useThemeStore'
import { logout } from '../lib/firebase'
import { api } from '../lib/api'
import { onForegroundPush } from '../lib/push'
import { displayName, initialsFor } from '../lib/format'

const NAV = [
  { to: '/overview', label: 'Overview', Icon: Home, end: true },
  { to: '/radar', label: 'AI Radar', Icon: RadarIcon },
  { to: '/flocks', label: 'Flocks', Icon: Bird },
  { to: '/houses', label: 'Houses', Icon: Warehouse },
  { to: '/checks', label: 'Flock Checks', Icon: ClipboardList },
  { to: '/alerts', label: 'Alerts', Icon: ShieldAlert, badge: true },
  { to: '/analytics', label: 'Analytics', Icon: BarChart3 },
  { to: '/ask', label: 'Ask FlockGuard', Icon: Sparkles },
]

const MANAGEMENT_NAV = [
  { to: '/team', label: 'Team', Icon: Users },
  { to: '/settings', label: 'Settings', Icon: Settings },
  { to: '/billing', label: 'Billing', Icon: CreditCard },
]

const MOBILE_NAV = [
  { to: '/overview', label: 'Home', Icon: Home, end: true },
  { to: '/radar', label: 'Radar', Icon: RadarIcon },
  { to: '/checks/new', label: 'CHECK', Icon: Plus, emphasize: true },
  { to: '/alerts', label: 'Alerts', Icon: ShieldAlert },
  { to: '/ask', label: 'AI', Icon: Sparkles },
]

const PUSH_TOAST_LIFETIME_MS = 8000

/** The backend sends the click-through URL as a full absolute URL (see
 * app.core.config.settings.app_public_url in push_service.py) since the
 * same value is reused for email links - react-router's navigate() wants
 * an in-app path, not a scheme+host, so this strips it down. */
function pathFromPushUrl(url) {
  try {
    return new URL(url).pathname
  } catch {
    return url || '/alerts'
  }
}

function navLinkClass(expanded) {
  return ({ isActive }) =>
    [
      'flex items-center gap-3 rounded-lg py-2 text-sm font-medium transition-colors',
      expanded ? 'px-3' : 'justify-center px-0',
      isActive ? 'bg-white/12 text-white' : 'text-white/60 hover:bg-white/5 hover:text-white',
    ].join(' ')
}

export default function AppLayout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [openAlertCount, setOpenAlertCount] = useState(0)
  const [sidebarPeek, setSidebarPeek] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [pushToasts, setPushToasts] = useState([])
  const hideTimeoutRef = useRef(null)
  const { user } = useAuthStore()
  const { currentFarmId } = useAppStore()
  const { theme, toggleTheme } = useThemeStore()
  const navigate = useNavigate()

  function showSidebar() {
    clearTimeout(hideTimeoutRef.current)
    setSidebarPeek(true)
  }

  function scheduleHideSidebar() {
    hideTimeoutRef.current = setTimeout(() => setSidebarPeek(false), 250)
  }

  useEffect(() => () => clearTimeout(hideTimeoutRef.current), [])

  useEffect(() => {
    if (!drawerOpen) return
    function handleKeyDown(e) {
      if (e.key === 'Escape') setDrawerOpen(false)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [drawerOpen])

  useEffect(() => {
    if (!currentFarmId) return
    let cancelled = false
    api.alerts.list({ resolved: false }).then((alerts) => {
      if (!cancelled) setOpenAlertCount(alerts.length)
    })
    return () => {
      cancelled = true
    }
  }, [currentFarmId])

  // Push notifications only produce a visible OS popup when the tab is
  // closed/backgrounded (see public/firebase-messaging-sw.js) - a push that
  // arrives while someone's already looking at FlockGuard is delivered here
  // instead (Firebase's "foreground message" path), so without this it
  // would otherwise silently do nothing.
  useEffect(() => {
    let unsubscribe = () => {}
    let cancelled = false
    onForegroundPush((payload) => {
      // Sent as a data-only message (see app/services/push_service.py) so
      // this always fires reliably instead of sometimes being routed to
      // the service worker's onBackgroundMessage even while focused.
      const { title, body, url } = payload.data || {}
      const id = `${Date.now()}-${Math.random()}`
      setPushToasts((prev) => [...prev, { id, title: title || 'FlockGuard', body, url }])
      setTimeout(() => setPushToasts((prev) => prev.filter((t) => t.id !== id)), PUSH_TOAST_LIFETIME_MS)
    }).then((unsub) => {
      if (cancelled) unsub()
      else unsubscribe = unsub
    })
    return () => {
      cancelled = true
      unsubscribe()
    }
  }, [])

  function dismissPushToast(id) {
    setPushToasts((prev) => prev.filter((t) => t.id !== id))
  }

  function openPushToast(toast) {
    dismissPushToast(toast.id)
    navigate(pathFromPushUrl(toast.url))
  }

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex min-h-screen bg-bg">
      {/* Reserves the collapsed rail's width in normal flow; the aside itself is fixed/overlaid so expanding it on hover never reflows this. */}
      <div className="hidden w-16 shrink-0 lg:block" />

      <aside
        onMouseEnter={showSidebar}
        onMouseLeave={scheduleHideSidebar}
        className={[
          'fixed inset-y-0 left-0 z-20 hidden flex-col bg-forest-dark py-4 shadow-xl transition-[width] duration-200 ease-out lg:flex',
          sidebarPeek ? 'w-60' : 'w-16',
        ].join(' ')}
      >
        <div className={`flex items-center gap-2 ${sidebarPeek ? 'px-4' : 'justify-center px-0'}`}>
          <LogoMark size={sidebarPeek ? 34 : 28} />
          {sidebarPeek ? (
            <span className="whitespace-nowrap font-display text-base font-extrabold text-white">FlockGuard</span>
          ) : null}
        </div>

        <nav className="mt-6 flex-1 space-y-0.5 px-3">
          {NAV.map(({ to, label, Icon, end, badge }) => (
            <NavLink key={to} to={to} end={end} className={navLinkClass(sidebarPeek)}>
              <span className="relative shrink-0">
                <Icon size={18} />
                {badge && openAlertCount > 0 ? (
                  <span className="absolute -right-1 -top-1 h-1.5 w-1.5 rounded-full bg-critical" />
                ) : null}
              </span>
              {sidebarPeek ? <span className="flex-1 whitespace-nowrap">{label}</span> : null}
            </NavLink>
          ))}

          {sidebarPeek ? (
            <p className="mt-6 px-3 text-xs font-bold uppercase tracking-wide text-white/30">
              Management
            </p>
          ) : (
            <div className="mx-3 mt-6 border-t border-white/10" />
          )}
          {MANAGEMENT_NAV.map(({ to, label, Icon }) => (
            <NavLink key={to} to={to} className={navLinkClass(sidebarPeek)}>
              <span className="shrink-0">
                <Icon size={18} />
              </span>
              {sidebarPeek ? <span className="whitespace-nowrap">{label}</span> : null}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto px-3">
          <div className="relative">
            <button
              onClick={() => setMenuOpen((v) => !v)}
              className={`flex w-full items-center gap-2 rounded-lg py-2.5 text-left hover:bg-white/5 ${
                sidebarPeek ? 'px-3' : 'justify-center px-0'
              }`}
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-forest text-xs font-bold text-white">
                {initialsFor(user)}
              </span>
              {sidebarPeek ? (
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-white">
                    {displayName(user)}
                  </span>
                  <span className="block text-xs text-white/50">Owner</span>
                </span>
              ) : null}
            </button>
            {menuOpen ? (
              <div className="absolute bottom-full left-0 mb-1 w-56 rounded border border-hairline bg-surface py-1 text-sm shadow-sm">
                <div className="truncate border-b border-hairline px-3 py-2 text-secondary">
                  {user?.email}
                </div>
                <button
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-navy hover:bg-forest/5"
                >
                  <LogOut size={14} />
                  Sign out
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </aside>

      <div className="flex flex-1 flex-col pb-16 lg:pb-0">
        <header className="flex items-center justify-between border-b border-hairline bg-surface px-4 py-3 lg:hidden">
          <div className="flex items-center gap-1">
            <button
              onClick={() => setDrawerOpen(true)}
              className="rounded-lg p-1.5 text-secondary hover:bg-forest/5 hover:text-navy"
              aria-label="Open menu"
            >
              <Menu size={22} />
            </button>
            <button
              onClick={() => navigate('/overview')}
              className="flex items-center gap-2 rounded-lg px-1.5 py-1"
            >
              <LogoMark size={26} />
              <span className="font-display text-sm font-extrabold text-navy">FlockGuard</span>
            </button>
          </div>
          <div className="flex items-center gap-3">
            <NavLink to="/alerts" className="relative text-secondary hover:text-navy" title="Alerts">
              <Bell size={20} />
              {openAlertCount > 0 ? (
                <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-critical" />
              ) : null}
            </NavLink>
            <button onClick={toggleTheme} className="text-secondary hover:text-navy" title="Toggle theme">
              {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
            </button>
          </div>
        </header>

        <div className="hidden items-center justify-end gap-4 border-b border-hairline bg-surface px-6 py-3 lg:flex">
          <button onClick={toggleTheme} className="text-secondary hover:text-navy" title="Toggle theme">
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          <NavLink to="/alerts" className="relative text-secondary hover:text-navy" title="Alerts">
            <Bell size={20} />
            {openAlertCount > 0 ? (
              <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-critical" />
            ) : null}
          </NavLink>
        </div>

        <main className="flex-1">
          <Outlet />
        </main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-10 flex border-t border-hairline bg-surface lg:hidden">
        {MOBILE_NAV.map(({ to, label, Icon, end, emphasize }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              [
                'flex flex-1 flex-col items-center gap-0.5 py-2 text-xs font-medium',
                emphasize ? '' : isActive ? 'text-forest' : 'text-secondary',
              ].join(' ')
            }
          >
            {emphasize ? (
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-forest text-white">
                <Icon size={18} />
              </span>
            ) : (
              <Icon size={18} />
            )}
            {label}
          </NavLink>
        ))}
      </nav>

      {drawerOpen ? (
        <div className="fixed inset-0 z-30 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setDrawerOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-[80%] flex-col bg-forest-dark py-4 shadow-xl">
            <div className="flex items-center justify-between px-4">
              <button
                onClick={() => {
                  setDrawerOpen(false)
                  navigate('/overview')
                }}
                className="flex items-center gap-2"
              >
                <LogoMark size={30} />
                <span className="font-display text-base font-extrabold text-white">FlockGuard</span>
              </button>
              <button
                onClick={() => setDrawerOpen(false)}
                className="rounded-lg p-1 text-white/60 hover:bg-white/5 hover:text-white"
                aria-label="Close menu"
              >
                <X size={20} />
              </button>
            </div>

            <nav className="mt-6 flex-1 space-y-0.5 overflow-y-auto px-3">
              {NAV.map(({ to, label, Icon, end, badge }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  onClick={() => setDrawerOpen(false)}
                  className={navLinkClass(true)}
                >
                  <span className="relative shrink-0">
                    <Icon size={18} />
                    {badge && openAlertCount > 0 ? (
                      <span className="absolute -right-1 -top-1 h-1.5 w-1.5 rounded-full bg-critical" />
                    ) : null}
                  </span>
                  <span className="flex-1 whitespace-nowrap">{label}</span>
                </NavLink>
              ))}

              <p className="mt-6 px-3 text-xs font-bold uppercase tracking-wide text-white/30">Management</p>
              {MANAGEMENT_NAV.map(({ to, label, Icon }) => (
                <NavLink key={to} to={to} onClick={() => setDrawerOpen(false)} className={navLinkClass(true)}>
                  <span className="shrink-0">
                    <Icon size={18} />
                  </span>
                  <span className="whitespace-nowrap">{label}</span>
                </NavLink>
              ))}
            </nav>

            <div className="mt-auto px-3 pt-3">
              <div className="flex items-center gap-2 rounded-lg px-3 py-2.5">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-forest text-xs font-bold text-white">
                  {initialsFor(user)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-white">{displayName(user)}</span>
                  <span className="block truncate text-xs text-white/50">{user?.email}</span>
                </span>
              </div>
              <button
                onClick={() => {
                  setDrawerOpen(false)
                  handleLogout()
                }}
                className="mt-1 flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm text-white/70 hover:bg-white/5 hover:text-white"
              >
                <LogOut size={16} />
                Sign out
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {pushToasts.length > 0 ? (
        <div className="fixed right-4 top-4 z-40 w-80 max-w-[calc(100vw-2rem)] space-y-2">
          {pushToasts.map((toast) => (
            <div
              key={toast.id}
              onClick={() => openPushToast(toast)}
              className="cursor-pointer rounded-xl border border-hairline bg-surface p-4 shadow-lg"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold text-navy">{toast.title}</p>
                  {toast.body ? <p className="mt-0.5 text-xs text-secondary">{toast.body}</p> : null}
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    dismissPushToast(toast.id)
                  }}
                  className="shrink-0 text-secondary hover:text-navy"
                  aria-label="Dismiss"
                >
                  <X size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}
