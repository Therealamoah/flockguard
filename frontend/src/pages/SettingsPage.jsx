import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Settings as SettingsIcon,
  MapPin,
  Clock3,
  Bell,
  Sparkles,
  User,
  AlertTriangle,
  Loader2,
  Mail,
  LogOut,
  Archive,
  ArchiveRestore,
  Lock,
} from 'lucide-react'
import { useAuthStore } from '../store/useAuthStore'
import { useAppStore } from '../store/useAppStore'
import { logout } from '../lib/firebase'
import { api } from '../lib/api'
import { enablePushNotifications, disablePushNotifications } from '../lib/push'

const TABS = [
  { key: 'profile', label: 'Farm Profile', Icon: MapPin },
  { key: 'schedule', label: 'Check times', Icon: Clock3 },
  { key: 'notifications', label: 'Notifications', Icon: Bell },
  { key: 'intelligence', label: 'AI help', Icon: Sparkles },
  { key: 'account', label: 'Account', Icon: User },
  { key: 'danger', label: 'Delete farm', Icon: AlertTriangle },
]

// The full IANA tz database, via the browser itself - the backend already
// validates against real IANA identifiers (ZoneInfo, see
// FarmSettingsUpdate._validate_timezone), so the picker should offer every
// zone it would accept, not a hand-picked shortlist. Falls back to a short,
// practical list for the rare browser without Intl.supportedValuesOf
// (Safari < 15.4) so the field still works, just with fewer choices.
const TIMEZONES =
  typeof Intl.supportedValuesOf === 'function'
    ? Intl.supportedValuesOf('timeZone')
    : [
        'Africa/Accra',
        'Africa/Lagos',
        'Africa/Nairobi',
        'Africa/Johannesburg',
        'Africa/Cairo',
        'Europe/London',
        'America/New_York',
        'America/Los_Angeles',
        'Asia/Dubai',
        'Asia/Kolkata',
      ]

function SaveButton({ status, disabled }) {
  return (
    <button
      type="submit"
      disabled={disabled || status === 'saving'}
      className="flex items-center gap-1.5 rounded-lg bg-forest px-4 py-2 text-sm font-bold text-white hover:bg-forest-dark disabled:opacity-60"
    >
      {status === 'saving' ? <Loader2 size={14} className="animate-spin" /> : null}
      {status === 'saving' ? 'Saving...' : 'Save'}
    </button>
  )
}

function SaveFeedback({ status }) {
  if (status === 'saved') return <span className="text-xs font-semibold text-normal">Saved ✓</span>
  if (status === 'error') return <span className="text-xs font-semibold text-critical">Could not save. Try again.</span>
  return null
}

function ReadOnlyNotice() {
  return (
    <p className="mb-4 flex items-center gap-1.5 rounded-lg bg-hairline/50 px-3 py-2 text-xs font-medium text-secondary">
      <Lock size={12} />
      Only owners and managers can change these settings.
    </p>
  )
}

function FarmProfileTab({ settings, canEdit, onSave }) {
  const [form, setForm] = useState({
    name: settings.name || '',
    country: settings.country || '',
    timezone: settings.timezone || '',
    temperature_unit: settings.temperature_unit,
    weight_unit: settings.weight_unit,
    contact_number: settings.contact_number || '',
  })
  const [status, setStatus] = useState('idle')

  async function handleSubmit(e) {
    e.preventDefault()
    setStatus('saving')
    try {
      await onSave({ ...form, timezone: form.timezone || null })
      setStatus('saved')
    } catch {
      setStatus('error')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-lg space-y-4">
      {!canEdit ? <ReadOnlyNotice /> : null}
      <div>
        <label className="mb-1 block text-sm font-semibold text-navy">Farm name</label>
        <input
          disabled={!canEdit}
          value={form.name}
          onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
          className="w-full rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest disabled:bg-hairline/30"
        />
      </div>
      <div>
        <label className="mb-1 block text-sm font-semibold text-navy">Country</label>
        <input
          disabled={!canEdit}
          value={form.country}
          onChange={(e) => setForm((f) => ({ ...f, country: e.target.value }))}
          placeholder="Ghana"
          className="w-full rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest disabled:bg-hairline/30"
        />
      </div>
      <div>
        <label className="mb-1 block text-sm font-semibold text-navy">Timezone</label>
        <select
          disabled={!canEdit}
          value={form.timezone}
          onChange={(e) => setForm((f) => ({ ...f, timezone: e.target.value }))}
          className="w-full rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest disabled:bg-hairline/30"
        >
          <option value="">Not set</option>
          {TIMEZONES.map((tz) => (
            <option key={tz} value={tz}>
              {tz}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-muted">
          So morning and evening checks match the right day, and reminders come at the right time.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-1 block text-sm font-semibold text-navy">Temperature unit</label>
          <select
            disabled={!canEdit}
            value={form.temperature_unit}
            onChange={(e) => setForm((f) => ({ ...f, temperature_unit: e.target.value }))}
            className="w-full rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest disabled:bg-hairline/30"
          >
            <option value="celsius">Celsius</option>
            <option value="fahrenheit">Fahrenheit</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-semibold text-navy">Weight unit</label>
          <select
            disabled={!canEdit}
            value={form.weight_unit}
            onChange={(e) => setForm((f) => ({ ...f, weight_unit: e.target.value }))}
            className="w-full rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest disabled:bg-hairline/30"
          >
            <option value="kg">kg</option>
            <option value="lb">lb</option>
          </select>
        </div>
      </div>
      <div>
        <label className="mb-1 block text-sm font-semibold text-navy">Farm contact number (optional)</label>
        <input
          disabled={!canEdit}
          value={form.contact_number}
          onChange={(e) => setForm((f) => ({ ...f, contact_number: e.target.value }))}
          className="w-full rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest disabled:bg-hairline/30"
        />
      </div>
      {canEdit ? (
        <div className="flex items-center gap-3">
          <SaveButton status={status} />
          <SaveFeedback status={status} />
        </div>
      ) : null}
    </form>
  )
}

function CheckWindowRow({ label, enabled, start, end, canEdit, onChange }) {
  return (
    <div className="rounded-xl border border-hairline p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-bold text-navy">{label}</span>
        <label className="flex items-center gap-2 text-xs font-semibold text-secondary">
          Enabled
          <input
            type="checkbox"
            disabled={!canEdit}
            checked={enabled}
            onChange={(e) => onChange({ enabled: e.target.checked })}
          />
        </label>
      </div>
      <div className="mt-3 flex items-center gap-2">
        <input
          type="time"
          disabled={!canEdit}
          value={start}
          onChange={(e) => onChange({ start: e.target.value })}
          className="rounded-lg border border-hairline px-2 py-1.5 text-sm outline-none focus:border-forest disabled:bg-hairline/30"
        />
        <span className="text-xs text-muted">to</span>
        <input
          type="time"
          disabled={!canEdit}
          value={end}
          onChange={(e) => onChange({ end: e.target.value })}
          className="rounded-lg border border-hairline px-2 py-1.5 text-sm outline-none focus:border-forest disabled:bg-hairline/30"
        />
      </div>
    </div>
  )
}

function CheckScheduleTab({ settings, canEdit, onSave }) {
  const [form, setForm] = useState({
    morning_check_enabled: settings.morning_check_enabled,
    morning_check_start: settings.morning_check_start,
    morning_check_end: settings.morning_check_end,
    evening_check_enabled: settings.evening_check_enabled,
    evening_check_start: settings.evening_check_start,
    evening_check_end: settings.evening_check_end,
  })
  const [status, setStatus] = useState('idle')

  async function handleSubmit(e) {
    e.preventDefault()
    setStatus('saving')
    try {
      await onSave(form)
      setStatus('saved')
    } catch {
      setStatus('error')
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-lg space-y-4">
      {!canEdit ? <ReadOnlyNotice /> : null}
      <CheckWindowRow
        label="Morning check"
        enabled={form.morning_check_enabled}
        start={form.morning_check_start}
        end={form.morning_check_end}
        canEdit={canEdit}
        onChange={(patch) =>
          setForm((f) => ({
            ...f,
            ...(patch.enabled !== undefined ? { morning_check_enabled: patch.enabled } : {}),
            ...(patch.start !== undefined ? { morning_check_start: patch.start } : {}),
            ...(patch.end !== undefined ? { morning_check_end: patch.end } : {}),
          }))
        }
      />
      <CheckWindowRow
        label="Evening check"
        enabled={form.evening_check_enabled}
        start={form.evening_check_start}
        end={form.evening_check_end}
        canEdit={canEdit}
        onChange={(patch) =>
          setForm((f) => ({
            ...f,
            ...(patch.enabled !== undefined ? { evening_check_enabled: patch.enabled } : {}),
            ...(patch.start !== undefined ? { evening_check_start: patch.start } : {}),
            ...(patch.end !== undefined ? { evening_check_end: patch.end } : {}),
          }))
        }
      />
      <p className="text-xs text-muted">
        You can always do an emergency check at any time. These times are only for reminders.
      </p>
      {canEdit ? (
        <div className="flex items-center gap-3">
          <SaveButton status={status} />
          <SaveFeedback status={status} />
        </div>
      ) : null}
    </form>
  )
}

function NotificationsTab({ settings, canEdit, onSave }) {
  const [prefs, setPrefs] = useState(settings.notification_preferences)
  const [status, setStatus] = useState('idle')
  const [pushStatus, setPushStatus] = useState('idle') // idle | requesting | error
  const [pushError, setPushError] = useState('')

  async function handlePushToggle(checked) {
    if (!checked) {
      setPrefs((p) => ({ ...p, channels: { ...p.channels, push: false } }))
      disablePushNotifications()
      return
    }
    setPushStatus('requesting')
    setPushError('')
    try {
      await enablePushNotifications()
      setPrefs((p) => ({ ...p, channels: { ...p.channels, push: true } }))
      setPushStatus('idle')
    } catch (err) {
      setPushStatus('error')
      setPushError(err.message || 'Could not enable push notifications on this device.')
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setStatus('saving')
    try {
      await onSave({ notification_preferences: prefs })
      setStatus('saved')
    } catch {
      setStatus('error')
    }
  }

  const toggles = [
    ['critical_alerts', 'Critical - very serious'],
    ['warning_alerts', 'Warning - serious'],
    ['watch_alerts', 'Watch - keep an eye on it'],
    ['morning_check_reminder', 'Remind me to do the morning check'],
    ['evening_check_reminder', 'Remind me to do the evening check'],
    ['daily_farm_brief', "Today's farm update"],
  ]

  return (
    <form onSubmit={handleSubmit} className="max-w-lg space-y-4">
      {!canEdit ? <ReadOnlyNotice /> : null}
      <div className="space-y-2 rounded-xl border border-hairline p-4">
        {toggles.map(([key, label]) => (
          <label key={key} className="flex items-center justify-between text-sm text-navy">
            {label}
            <input
              type="checkbox"
              disabled={!canEdit}
              checked={prefs[key]}
              onChange={(e) => setPrefs((p) => ({ ...p, [key]: e.target.checked }))}
            />
          </label>
        ))}
      </div>

      <div>
        <h3 className="text-sm font-bold text-navy">Channels</h3>
        <p className="mt-1 text-xs text-secondary">
          We send an email or phone notification when a new warning comes up, for the types you switched on above.
        </p>
        <div className="mt-2 space-y-2 rounded-xl border border-hairline p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-navy">In-app</span>
            <span className="rounded-full bg-normal/10 px-2 py-0.5 text-xs font-semibold text-normal">Available</span>
          </div>
          <div>
            <label className="flex items-center justify-between text-sm text-navy">
              <span className="flex items-center gap-1.5">
                Push
                <span className="rounded-full bg-normal/10 px-1.5 py-0.5 text-[10px] font-semibold text-normal">
                  Available
                </span>
              </span>
              <input
                type="checkbox"
                disabled={!canEdit || pushStatus === 'requesting'}
                checked={Boolean(prefs.channels?.push)}
                onChange={(e) => handlePushToggle(e.target.checked)}
              />
            </label>
            {pushStatus === 'requesting' ? (
              <p className="mt-1 text-xs text-secondary">Asking your phone for permission...</p>
            ) : null}
            {pushStatus === 'error' ? <p className="mt-1 text-xs text-critical">{pushError}</p> : null}
          </div>
          <label className="flex items-center justify-between text-sm text-navy">
            <span className="flex items-center gap-1.5">
              Email
              <span className="rounded-full bg-normal/10 px-1.5 py-0.5 text-[10px] font-semibold text-normal">
                Available
              </span>
            </span>
            <input
              type="checkbox"
              disabled={!canEdit}
              checked={Boolean(prefs.channels?.email)}
              onChange={(e) =>
                setPrefs((p) => ({ ...p, channels: { ...p.channels, email: e.target.checked } }))
              }
            />
          </label>
        </div>
      </div>

      {canEdit ? (
        <div className="flex items-center gap-3">
          <SaveButton status={status} />
          <SaveFeedback status={status} />
        </div>
      ) : null}
    </form>
  )
}

function IntelligenceTab({ settings, canEdit, onSave }) {
  const [prefs, setPrefs] = useState(settings.ai_preferences)
  const [status, setStatus] = useState('idle')

  async function handleSubmit(e) {
    e.preventDefault()
    setStatus('saving')
    try {
      await onSave({ ai_preferences: prefs })
      setStatus('saved')
    } catch {
      setStatus('error')
    }
  }

  const toggles = [
    ['ai_explanations_enabled', 'Explain warnings', 'The AI tells you in simple words why a check or house needs a look.'],
    ['daily_ai_brief_enabled', 'Friendly daily update', "The AI writes your farm's daily update like a short chat."],
    ['proactive_insights_enabled', 'Spot problems early', 'FlockGuard tells you when something keeps getting worse, e.g. birds eating less feed every day.'],
  ]

  return (
    <form onSubmit={handleSubmit} className="max-w-lg space-y-4">
      {!canEdit ? <ReadOnlyNotice /> : null}
      <div className="space-y-3 rounded-xl border border-hairline p-4">
        {toggles.map(([key, label, hint]) => (
          <label key={key} className="flex items-start justify-between gap-3 text-sm">
            <span>
              <span className="block font-semibold text-navy">{label}</span>
              <span className="block text-xs text-secondary">{hint}</span>
            </span>
            <input
              type="checkbox"
              disabled={!canEdit}
              checked={prefs[key]}
              onChange={(e) => setPrefs((p) => ({ ...p, [key]: e.target.checked }))}
            />
          </label>
        ))}
      </div>

      <div className="rounded-xl border border-hairline bg-bg p-4">
        <p className="text-xs font-bold uppercase tracking-wide text-secondary">How the risk number works</p>
        <p className="mt-1 text-sm font-bold text-navy">{settings.risk_method.name}</p>
        <p className="mt-1 text-sm text-secondary">{settings.risk_method.description}</p>
        <p className="mt-2 text-xs text-muted">{settings.risk_method.disclaimer}</p>
      </div>

      {canEdit ? (
        <div className="flex items-center gap-3">
          <SaveButton status={status} />
          <SaveFeedback status={status} />
        </div>
      ) : null}
    </form>
  )
}

function AccountTab({ user }) {
  const [name, setName] = useState(user?.displayName || '')
  const [status, setStatus] = useState('idle')
  const [resetSent, setResetSent] = useState(false)
  const navigate = useNavigate()

  async function handleSaveName(e) {
    e.preventDefault()
    setStatus('saving')
    try {
      await api.settings.updateAccount(name)
      setStatus('saved')
    } catch {
      setStatus('error')
    }
  }

  async function handleResetPassword() {
    if (!user?.email) return
    await api.auth.forgotPassword(user.email)
    setResetSent(true)
  }

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="max-w-lg space-y-6">
      <form onSubmit={handleSaveName} className="space-y-3 rounded-xl border border-hairline p-4">
        <div>
          <label className="mb-1 block text-sm font-semibold text-navy">Display name</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-forest"
          />
        </div>
        <p className="flex items-center gap-2 text-sm text-secondary">
          <Mail size={15} className="text-muted" />
          {user?.email}
        </p>
        <div className="flex items-center gap-3">
          <SaveButton status={status} />
          <SaveFeedback status={status} />
        </div>
      </form>

      <div className="rounded-xl border border-hairline p-4">
        <h3 className="text-sm font-bold text-navy">Password</h3>
        <p className="mt-1 text-sm text-secondary">
          We'll email you a secure link to set a new password.
        </p>
        <button
          onClick={handleResetPassword}
          className="mt-3 rounded-lg border border-hairline px-4 py-2 text-sm font-bold text-navy hover:bg-forest/5"
        >
          Send password reset email
        </button>
        {resetSent ? <p className="mt-2 text-sm text-normal">Reset email sent ✓</p> : null}
      </div>

      <button
        onClick={handleLogout}
        className="flex items-center gap-1.5 rounded-lg border border-hairline px-4 py-2 text-sm font-bold text-critical hover:bg-critical/5"
      >
        <LogOut size={15} />
        Sign out
      </button>
    </div>
  )
}

function DangerZoneTab({ farmId, farmName, isOwner, settings, setSettings }) {
  const [confirmation, setConfirmation] = useState('')
  const [message, setMessage] = useState('')
  const [isBusy, setIsBusy] = useState(false)

  if (!isOwner) {
    return (
      <div className="max-w-lg rounded-xl border border-hairline bg-surface p-6 text-center">
        <Lock size={24} className="mx-auto text-muted" />
        <p className="mt-2 text-sm font-semibold text-navy">Only the farm owner can access this section.</p>
      </div>
    )
  }

  async function handleArchiveToggle() {
    setIsBusy(true)
    setMessage('')
    try {
      if (settings.archived) {
        const result = await api.settings.unarchiveFarm(farmId)
        setSettings((prev) => ({ ...prev, archived: result.archived }))
      } else {
        const result = await api.settings.archiveFarm(farmId)
        setSettings((prev) => ({ ...prev, archived: result.archived }))
      }
    } catch {
      setMessage('Could not update the farm right now. Try again.')
    } finally {
      setIsBusy(false)
    }
  }

  async function handleDelete() {
    setIsBusy(true)
    setMessage('')
    try {
      await api.settings.deleteFarm(farmId, confirmation)
    } catch (err) {
      setMessage(
        err.message.includes('501')
          ? "Deleting a farm for good is not available yet. Your farm has NOT been deleted. Use Archive instead - you can undo it later."
          : 'Confirmation text did not match the farm name or "DELETE".'
      )
    } finally {
      setIsBusy(false)
      setConfirmation('')
    }
  }

  return (
    <div className="max-w-lg space-y-4">
      <div className="rounded-xl border border-hairline p-4">
        <h3 className="text-sm font-bold text-navy">{settings.archived ? 'Unarchive Farm' : 'Archive Farm'}</h3>
        <p className="mt-1 text-sm text-secondary">
          {settings.archived
            ? 'This farm is currently archived. Unarchiving restores normal access.'
            : 'Hides this farm from active use without deleting anything - fully reversible.'}
        </p>
        <button
          onClick={handleArchiveToggle}
          disabled={isBusy}
          className="mt-3 flex items-center gap-1.5 rounded-lg border border-hairline px-4 py-2 text-sm font-bold text-navy hover:bg-forest/5 disabled:opacity-60"
        >
          {settings.archived ? <ArchiveRestore size={15} /> : <Archive size={15} />}
          {settings.archived ? 'Unarchive Farm' : 'Archive Farm'}
        </button>
      </div>

      <div className="rounded-xl border border-critical/30 bg-critical/5 p-4">
        <h3 className="text-sm font-bold text-critical">Delete Farm</h3>
        <p className="mt-1 text-sm text-secondary">
          Permanently deletes this farm and everything in it. This action cannot be undone.
        </p>
        <p className="mt-1 text-xs text-muted">
          Type <strong>{farmName}</strong> or <strong>DELETE</strong> to confirm.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <input
            value={confirmation}
            onChange={(e) => setConfirmation(e.target.value)}
            placeholder={farmName}
            className="flex-1 rounded-lg border border-hairline px-3 py-2 text-sm outline-none focus:border-critical"
          />
          <button
            onClick={handleDelete}
            disabled={isBusy || !confirmation}
            className="rounded-lg bg-critical px-4 py-2 text-sm font-bold text-white hover:opacity-90 disabled:opacity-50"
          >
            Delete Farm
          </button>
        </div>
        {message ? <p className="mt-3 text-sm text-secondary">{message}</p> : null}
      </div>
    </div>
  )
}

export default function SettingsPage() {
  const { user } = useAuthStore()
  const { farms } = useAppStore()
  const farmId = farms[0]?.id

  const [tab, setTab] = useState('profile')
  const [settings, setSettings] = useState(null)
  const [myRole, setMyRole] = useState(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!farmId) {
      setIsLoading(false)
      return
    }
    let cancelled = false
    Promise.all([api.settings.get(farmId), api.team.get().catch(() => null)]).then(([data, team]) => {
      if (cancelled) return
      setSettings(data)
      if (team) {
        const mine = team.members.find((m) => m.id === user?.uid)
        setMyRole(mine?.role || null)
      }
      setIsLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [farmId, user?.uid])

  const canEdit = myRole === 'owner' || myRole === 'manager'
  const isOwner = myRole === 'owner'

  async function saveFields(fields) {
    const updated = await api.settings.update(farmId, fields)
    setSettings((prev) => ({ ...prev, ...updated }))
    return updated
  }

  return (
    <div className="mx-auto max-w-4xl p-6">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
          <SettingsIcon size={20} />
        </span>
        <h1 className="font-display text-2xl font-extrabold text-navy">Settings</h1>
      </div>

      {!farmId ? (
        <p className="mt-6 text-sm text-secondary">Set up a farm first to configure these settings.</p>
      ) : isLoading ? (
        <div className="mt-6 flex items-center justify-center gap-2 py-16 text-sm text-secondary">
          <Loader2 size={16} className="animate-spin" />
          Loading settings...
        </div>
      ) : (
        <>
          <div className="mt-6 flex flex-wrap gap-1 overflow-x-auto border-b border-hairline">
            {TABS.map(({ key, label, Icon }) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={[
                  'flex shrink-0 items-center gap-1.5 rounded-t-lg px-3 py-2 text-sm font-semibold transition-colors',
                  tab === key ? 'border-b-2 border-forest text-forest' : 'text-secondary hover:text-navy',
                ].join(' ')}
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </div>

          <div className="mt-6">
            {tab === 'profile' ? <FarmProfileTab settings={settings} canEdit={canEdit} onSave={saveFields} /> : null}
            {tab === 'schedule' ? <CheckScheduleTab settings={settings} canEdit={canEdit} onSave={saveFields} /> : null}
            {tab === 'notifications' ? (
              <NotificationsTab settings={settings} canEdit={canEdit} onSave={saveFields} />
            ) : null}
            {tab === 'intelligence' ? (
              <IntelligenceTab settings={settings} canEdit={canEdit} onSave={saveFields} />
            ) : null}
            {tab === 'account' ? <AccountTab user={user} /> : null}
            {tab === 'danger' ? (
              <DangerZoneTab farmId={farmId} farmName={farms[0]?.name} isOwner={isOwner} settings={settings} setSettings={setSettings} />
            ) : null}
          </div>
        </>
      )}
    </div>
  )
}
