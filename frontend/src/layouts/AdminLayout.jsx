import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Activity,
  Briefcase,
  Mail,
  ClipboardList,
  Building2,
  Users,
  Sparkles,
  ScrollText,
  ArrowLeft,
  LogOut,
  Sun,
  Moon,
  Menu,
  X,
} from 'lucide-react'
import LogoMark from '../components/Logo'
import { useAuthStore } from '../store/useAuthStore'
import { useThemeStore } from '../store/useThemeStore'
import { logout } from '../lib/firebase'

const NAV = [
  { to: '/admin', label: 'Overview', Icon: LayoutDashboard, end: true },
  { to: '/admin/summary', label: 'Summary', Icon: ClipboardList },
  { to: '/admin/activity', label: 'Activity', Icon: Activity },
  { to: '/admin/orgs', label: 'Organizations', Icon: Building2 },
  { to: '/admin/users', label: 'Users', Icon: Users },
  { to: '/admin/enterprise', label: 'Enterprise', Icon: Briefcase },
  { to: '/admin/ai-usage', label: 'AI usage', Icon: Sparkles },
  { to: '/admin/emails', label: 'Emails', Icon: Mail },
  { to: '/admin/audit-log', label: 'Audit log', Icon: ScrollText },
]

const navLinkClass = ({ isActive }) =>
  [
    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
    isActive ? 'bg-white/12 text-white' : 'text-white/60 hover:bg-white/5 hover:text-white',
  ].join(' ')

function SidebarContent({ onNavigate }) {
  const { user } = useAuthStore()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <>
      <div className="flex items-center gap-2 px-4">
        <LogoMark size={30} />
        <div>
          <span className="block font-display text-base font-extrabold leading-tight text-white">FlockGuard</span>
          <span className="block text-[10px] font-bold uppercase tracking-widest text-white/40">Admin console</span>
        </div>
      </div>

      <nav className="mt-6 flex-1 space-y-0.5 px-3">
        {NAV.map(({ to, label, Icon, end }) => (
          <NavLink key={to} to={to} end={end} onClick={onNavigate} className={navLinkClass}>
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto space-y-1 px-3">
        <NavLink
          to="/overview"
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-white/60 hover:bg-white/5 hover:text-white"
        >
          <ArrowLeft size={16} />
          Back to farm app
        </NavLink>
        <div className="truncate px-3 pt-2 text-xs text-white/40">{user?.email}</div>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm text-white/60 hover:bg-white/5 hover:text-white"
        >
          <LogOut size={16} />
          Sign out
        </button>
      </div>
    </>
  )
}

export default function AdminLayout() {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const { theme, toggleTheme } = useThemeStore()

  return (
    <div className="flex min-h-screen bg-bg">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col bg-forest-dark py-4 lg:flex">
        <SidebarContent />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-hairline bg-surface px-4 py-3 lg:px-6">
          <button
            onClick={() => setDrawerOpen(true)}
            className="rounded-lg p-1.5 text-secondary hover:bg-forest/5 hover:text-navy lg:hidden"
            aria-label="Open menu"
          >
            <Menu size={22} />
          </button>
          <span className="rounded-full bg-ai/10 px-2.5 py-1 text-xs font-bold text-ai">Platform admin</span>
          <button onClick={toggleTheme} className="text-secondary hover:text-navy" title="Toggle theme">
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
        </header>

        <main className="flex-1">
          <Outlet />
        </main>
      </div>

      {drawerOpen ? (
        <div className="fixed inset-0 z-30 lg:hidden">
          <div className="absolute inset-0 bg-black/40" onClick={() => setDrawerOpen(false)} />
          <div className="absolute inset-y-0 left-0 flex w-72 max-w-[80%] flex-col bg-forest-dark py-4 shadow-xl">
            <button
              onClick={() => setDrawerOpen(false)}
              className="absolute right-3 top-4 rounded-lg p-1 text-white/60 hover:bg-white/5 hover:text-white"
              aria-label="Close menu"
            >
              <X size={20} />
            </button>
            <SidebarContent onNavigate={() => setDrawerOpen(false)} />
          </div>
        </div>
      ) : null}
    </div>
  )
}
