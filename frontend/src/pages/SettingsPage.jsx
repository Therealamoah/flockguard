import { useNavigate } from 'react-router-dom'
import { Settings, Mail, LogOut, Warehouse } from 'lucide-react'
import { useAuthStore } from '../store/useAuthStore'
import { useAppStore } from '../store/useAppStore'
import { logout } from '../lib/firebase'

export default function SettingsPage() {
  const { user } = useAuthStore()
  const { farms, houses } = useAppStore()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
          <Settings size={20} />
        </span>
        <h1 className="font-display text-2xl font-extrabold text-navy">Settings</h1>
      </div>

      <section className="mt-6 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
        <h2 className="text-sm font-bold text-navy">Account</h2>
        <p className="mt-3 flex items-center gap-2 text-sm text-navy/70">
          <Mail size={15} className="text-navy/40" />
          {user?.email}
        </p>
        <button
          onClick={handleLogout}
          className="mt-4 flex items-center gap-1.5 rounded-lg border border-hairline px-4 py-2 text-sm font-bold text-critical hover:bg-critical/5"
        >
          <LogOut size={15} />
          Sign out
        </button>
      </section>

      <section className="mt-4 rounded-xl border border-hairline bg-surface p-5 shadow-sm">
        <h2 className="text-sm font-bold text-navy">Farm</h2>
        <p className="mt-3 flex items-center gap-2 text-sm text-navy/70">
          <Warehouse size={15} className="text-navy/40" />
          {farms[0]?.name || '—'}
        </p>
        <p className="mt-1 text-xs text-navy/50">{houses.length} house{houses.length === 1 ? '' : 's'}</p>
      </section>
    </div>
  )
}
