import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertOctagon,
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  ClipboardList,
  Download,
  Info,
  Minus,
  RefreshCw,
  Search,
  Siren,
  UserPlus,
  Users,
} from 'lucide-react'
import { api } from '../../lib/api'
import { timeAgo } from '../../lib/time'
import { Card, ErrorBlock, LoadingBlock, PageHeader, PlanBadge } from '../../components/admin/AdminUI'
import { shortDate } from '../../lib/adminFormat'
import { useAdminData } from '../../lib/useAdminData'

const SEVERITY = {
  critical: { Icon: AlertOctagon, className: 'text-critical bg-critical/10' },
  warning: { Icon: AlertTriangle, className: 'text-warning bg-warning/10' },
  info: { Icon: Info, className: 'text-ai bg-ai/10' },
}

const STAGE_STYLE = {
  suspended: 'bg-critical/10 text-critical',
  payment_issue: 'bg-critical/10 text-critical',
  health_risk: 'bg-critical/10 text-critical',
  inactive: 'bg-warning/10 text-warning',
  slipping: 'bg-warning/10 text-warning',
  setting_up: 'bg-ai/10 text-ai',
  active: 'bg-normal/10 text-normal',
}

const WEEK_CARDS = [
  { key: 'signups', label: 'New sign-ups', Icon: UserPlus },
  { key: 'active_users', label: 'Active users', Icon: Users },
  { key: 'flock_checks', label: 'Flock checks', Icon: ClipboardList },
  // More alerts is bad news, so its arrow colours are flipped.
  { key: 'alerts_raised', label: 'Alerts raised', Icon: Siren, lowerIsBetter: true },
]

function WeekCard({ label, Icon, values, lowerIsBetter }) {
  const { this_week: now, last_week: before } = values
  const diff = now - before
  const good = lowerIsBetter ? diff < 0 : diff > 0
  const DeltaIcon = diff === 0 ? Minus : diff > 0 ? ArrowUpRight : ArrowDownRight
  const color = diff === 0 ? 'text-muted' : good ? 'text-normal' : 'text-critical'
  return (
    <div className="rounded-lg border border-hairline bg-surface p-4 shadow-sm">
      <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-secondary">
        <Icon size={13} />
        {label}
      </p>
      <p className="mt-2 font-display text-2xl font-extrabold text-navy">{now}</p>
      <p className={`mt-0.5 flex items-center gap-1 text-xs font-medium ${color}`}>
        <DeltaIcon size={13} />
        {diff === 0 ? 'same as' : `${Math.abs(diff)} ${diff > 0 ? 'more than' : 'fewer than'}`} last week ({before})
      </p>
    </div>
  )
}

function AttentionList({ items }) {
  if (items.length === 0) {
    return <p className="py-6 text-center text-sm text-muted">Nothing needs your attention right now. 🎉</p>
  }
  return (
    <ul className="divide-y divide-hairline">
      {items.map((item, i) => {
        const { Icon, className } = SEVERITY[item.severity]
        const body = (
          <>
            <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${className}`}>
              <Icon size={16} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-semibold text-navy">{item.title}</span>
              <span className="block text-sm text-secondary">{item.detail}</span>
            </span>
            {item.link ? <ArrowRight size={15} className="mt-1 shrink-0 text-muted" /> : null}
          </>
        )
        return (
          <li key={`${item.kind}-${item.org_id}-${i}`}>
            {item.link ? (
              <Link to={item.link} className="-mx-2 flex items-start gap-3 rounded-lg px-2 py-3 hover:bg-forest/5">
                {body}
              </Link>
            ) : (
              <div className="flex items-start gap-3 py-3">{body}</div>
            )}
          </li>
        )
      })}
    </ul>
  )
}

function downloadCsv(farmers) {
  const header = ['Farm', 'Owner', 'Email', 'Plan', 'Status', 'Why', 'Houses', 'Team', 'Checks (7d)',
    'Checks (30d)', 'Open alerts', 'Last check', 'Last in app', 'Joined']
  const rows = farmers.map((f) => [f.name, f.owner_name || '', f.owner_email || '', f.plan, f.stage_label, f.reason,
    f.houses, f.members, f.checks_7d, f.checks_30d, f.open_alerts, f.last_check_at || '', f.last_seen_at || '',
    f.created_at || ''])
  const csv = [header, ...rows].map((r) => r.map((v) => `"${String(v).replaceAll('"', '""')}"`).join(',')).join('\n')
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
  const a = document.createElement('a')
  a.href = url
  a.download = `flockguard-farmers-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

export default function AdminBriefingPage() {
  const { data, error, isLoading, reload } = useAdminData(api.admin.briefing)
  const [stage, setStage] = useState('all')
  const [query, setQuery] = useState('')

  const farmers = useMemo(() => {
    if (!data) return []
    const q = query.trim().toLowerCase()
    return data.farmers.filter(
      (f) =>
        (stage === 'all' || f.stage === stage) &&
        (!q || `${f.name} ${f.owner_email || ''} ${f.owner_name || ''}`.toLowerCase().includes(q)),
    )
  }, [data, stage, query])

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 lg:p-6">
      <PageHeader Icon={ClipboardList} title="Summary" subtitle="How the week went, what needs you, and where every farmer stands.">
        <button
          onClick={reload}
          className="flex items-center gap-1.5 rounded-lg border border-hairline bg-surface px-3 py-2 text-sm font-semibold text-secondary hover:text-navy"
        >
          <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </PageHeader>

      {error ? <ErrorBlock message={error} onRetry={reload} /> : null}
      {!data && isLoading ? <LoadingBlock /> : null}

      {data ? (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {WEEK_CARDS.map((c) => (
              <WeekCard key={c.key} {...c} values={data.week[c.key]} />
            ))}
          </div>

          <Card
            title={`Needs your attention (${data.attention.length})`}
            action={<span className="text-xs text-muted">most urgent first</span>}
          >
            <AttentionList items={data.attention} />
          </Card>

          <Card
            title={`Farmers (${data.farmers.length})`}
            action={
              <button
                onClick={() => downloadCsv(farmers)}
                disabled={farmers.length === 0}
                className="flex items-center gap-1.5 text-xs font-bold text-forest hover:underline disabled:opacity-50"
              >
                <Download size={13} />
                Export CSV
              </button>
            }
          >
            <div className="mb-3 flex flex-wrap gap-1.5">
              <button
                onClick={() => setStage('all')}
                className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                  stage === 'all' ? 'bg-forest text-white' : 'text-secondary hover:bg-forest/5'
                }`}
              >
                All {data.farmers.length}
              </button>
              {Object.entries(data.stage_labels)
                .filter(([key]) => data.stage_counts[key] > 0)
                .map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setStage(key)}
                    className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                      stage === key ? 'bg-forest text-white' : STAGE_STYLE[key]
                    }`}
                  >
                    {label} {data.stage_counts[key]}
                  </button>
                ))}
            </div>

            <div className="relative mb-3">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search farm, owner or email..."
                className="w-full rounded-lg border border-hairline bg-surface py-2 pl-9 pr-3 text-sm text-navy outline-none focus:border-forest"
              />
            </div>

            {farmers.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted">No farmers match.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[820px] text-sm">
                  <thead className="text-left text-xs text-muted">
                    <tr>
                      <th className="pb-2 font-semibold">Farm</th>
                      <th className="pb-2 font-semibold">Status</th>
                      <th className="pb-2 font-semibold">Plan</th>
                      <th className="pb-2 font-semibold">Houses</th>
                      <th className="pb-2 font-semibold">Checks 7d / 30d</th>
                      <th className="pb-2 font-semibold">Alerts</th>
                      <th className="pb-2 font-semibold">Last in app</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-hairline">
                    {farmers.map((f) => (
                      <tr key={f.org_id} className="align-top">
                        <td className="max-w-[220px] py-2.5 pr-3">
                          <Link to={`/admin/orgs/${f.org_id}`} className="block truncate font-semibold text-navy hover:text-forest">
                            {f.name}
                          </Link>
                          <span className="block truncate text-xs text-muted">
                            {f.owner_email || 'no owner email'} · joined {shortDate(f.created_at)}
                          </span>
                        </td>
                        <td className="max-w-[260px] py-2.5 pr-3">
                          <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${STAGE_STYLE[f.stage]}`}>
                            {f.stage_label}
                          </span>
                          <span className="mt-1 block text-xs text-secondary">{f.reason}</span>
                        </td>
                        <td className="py-2.5 pr-3">
                          <PlanBadge plan={f.plan} comped={f.comped} />
                        </td>
                        <td className="py-2.5 pr-3 tabular-nums text-secondary">{f.houses}</td>
                        <td className="py-2.5 pr-3 tabular-nums text-secondary">
                          {f.checks_7d} / {f.checks_30d}
                          <span className="block text-xs text-muted">last {timeAgo(f.last_check_at) || 'never'}</span>
                        </td>
                        <td className="py-2.5 pr-3 tabular-nums">
                          {f.critical_open_alerts ? (
                            <span className="font-bold text-critical">{f.open_alerts} ({f.critical_open_alerts} critical)</span>
                          ) : (
                            <span className="text-secondary">{f.open_alerts}</span>
                          )}
                        </td>
                        <td className="py-2.5 text-xs text-secondary">{timeAgo(f.last_seen_at) || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
          <p className="text-xs text-muted">
            Updated {timeAgo(data.generated_at)}. Weeks are rolling 7-day windows. Every flag comes from records in the
            app - nothing is estimated.
          </p>
        </>
      ) : null}
    </div>
  )
}
