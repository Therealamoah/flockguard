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
} from 'lucide-react'
import LogoMark from '../components/Logo'
import { useAuthStore } from '../store/useAuthStore'
import { useAppStore } from '../store/useAppStore'
import { logout } from '../lib/firebase'
import { api } from '../lib/api'
import { displayName, initialsFor } from '../lib/format'

const NAV = [
  { to: '/', label: 'Overview', Icon: Home, end: true },
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
  { to: '/', label: 'Home', Icon: Home, end: true },
  { to: '/radar', label: 'Radar', Icon: RadarIcon },
  { to: '/checks/new', label: 'CHECK', Icon: Plus, emphasize: true },
  { to: '/alerts', label: 'Alerts', Icon: ShieldAlert },
  { to: '/ask', label: 'AI', Icon: Sparkles },
]

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
  const hideTimeoutRef = useRef(null)
  const { user } = useAuthStore()
  const { currentFarmId } = useAppStore()
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
    if (!currentFarmId) return
    let cancelled = false
    api.alerts.list({ resolved: false }).then((alerts) => {
      if (!cancelled) setOpenAlertCount(alerts.length)
    })
    return () => {
      cancelled = true
    }
  }, [currentFarmId])

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex min-h-screen bg-bg">
      {/* Reserves the collapsed rail's width in normal flow; the aside itself is fixed/overlaid so expanding it on hover never reflows this. */}
      <div className="hidden w-16 shrink-0 md:block" />

      <aside
        onMouseEnter={showSidebar}
        onMouseLeave={scheduleHideSidebar}
        className={[
          'fixed inset-y-0 left-0 z-20 hidden flex-col bg-forest-dark py-4 shadow-xl transition-[width] duration-200 ease-out md:flex',
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
                <div className="truncate border-b border-hairline px-3 py-2 text-navy/60">
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

      <div className="flex flex-1 flex-col pb-16 md:pb-0">
        <header className="flex items-center justify-end border-b border-hairline bg-surface px-6 py-3 md:hidden">
          <div className="flex items-center gap-2">
            <LogoMark size={28} />
            <span className="font-display text-sm font-extrabold text-navy">FlockGuard</span>
          </div>
        </header>

        <div className="hidden justify-end border-b border-hairline bg-surface px-6 py-3 md:flex">
          <NavLink to="/alerts" className="relative text-navy/60 hover:text-navy" title="Alerts">
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

      <nav className="fixed inset-x-0 bottom-0 z-10 flex border-t border-hairline bg-surface md:hidden">
        {MOBILE_NAV.map(({ to, label, Icon, end, emphasize }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              [
                'flex flex-1 flex-col items-center gap-0.5 py-2 text-xs font-medium',
                emphasize ? '' : isActive ? 'text-forest' : 'text-navy/60',
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
    </div>
  )
}
