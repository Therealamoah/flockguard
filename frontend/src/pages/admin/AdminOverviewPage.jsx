import { Link } from 'react-router-dom'
import {
  LayoutDashboard,
  Building2,
  Activity,
  Warehouse,
  Banknote,
  Sparkles,
  ShieldAlert,
  Users,
  RefreshCw,
  Radio,
  CalendarRange,
} from 'lucide-react'
import StatCard from '../../components/StatCard'
import { api } from '../../lib/api'
import { Card, CountBars, ErrorBlock, LoadingBlock, PageHeader, PlanBadge, UsageBar } from '../../components/admin/AdminUI'
import { dayLabel, ghs, shortDate } from '../../lib/adminFormat'
import { useAdminData } from '../../lib/useAdminData'

function CardLink({ to, children }) {
  return (
    <Link
      to={to}
      className="block rounded-lg transition hover:-translate-y-0.5 hover:shadow-md focus-visible:outline-2 focus-visible:outline-forest"
    >
      {children}
    </Link>
  )
}

const monthLabel = (m) => new Date(`${m}-01T00:00:00`).toLocaleDateString([], { month: 'short' })

export default function AdminOverviewPage() {
  const { data, error, isLoading, reload } = useAdminData(api.admin.overview)
  const { data: activity, reload: reloadActivity } = useAdminData(api.admin.activity)
  const at = activity?.totals

  const t = data?.totals
  const planRows = data ? Object.entries(data.plan_distribution).sort((a, b) => b[1] - a[1]) : []

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 lg:p-6">
      <PageHeader
        Icon={LayoutDashboard}
        title="Platform overview"
        subtitle="Every organization on FlockGuard, at a glance."
      >
        <button
          onClick={() => {
            reload()
            reloadActivity()
          }}
          className="flex items-center gap-1.5 rounded-lg border border-hairline bg-surface px-3 py-2 text-sm font-semibold text-secondary hover:text-navy"
        >
          <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          Refresh
        </button>
      </PageHeader>

      {error ? <ErrorBlock message={error} onRetry={reload} /> : null}
      {!data && isLoading ? <LoadingBlock /> : null}

      {t ? (
        <>
          {at ? (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <CardLink to="/admin/activity">
                <StatCard
                  label="Online now"
                  value={at.online_now}
                  caption={`in the last ${activity.online_window_minutes} min`}
                  captionColor="var(--color-muted)"
                  Icon={Radio}
                  iconColor="#2F9E58"
                />
              </CardLink>
              <CardLink to="/admin/activity">
                <StatCard label="Active today" value={at.dau} caption={`${at.wau} this week`} captionColor="var(--color-muted)" Icon={Users} />
              </CardLink>
              <CardLink to="/admin/activity">
                <StatCard
                  label="Active this month"
                  value={at.mau}
                  caption={at.stickiness === null ? 'no activity yet' : `${Math.round(at.stickiness * 100)}% come back daily`}
                  captionColor="var(--color-muted)"
                  Icon={CalendarRange}
                />
              </CardLink>
              <CardLink to="/admin/activity">
                <StatCard
                  label="Dormant users"
                  value={at.dormant}
                  caption={`no visit in ${activity.dormant_after_days}+ days`}
                  captionColor={at.dormant ? 'var(--color-warning)' : 'var(--color-muted)'}
                  Icon={Activity}
                />
              </CardLink>
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <CardLink to="/admin/orgs">
              <StatCard
                label="Organizations"
                value={t.organizations}
                caption={t.suspended_orgs ? `${t.suspended_orgs} suspended` : `${t.members} active users`}
                captionColor={t.suspended_orgs ? 'var(--color-critical)' : 'var(--color-muted)'}
                Icon={Building2}
              />
            </CardLink>
            <CardLink to="/admin/orgs?sort=activity">
              <StatCard
                label="Active (7 days)"
                value={t.active_orgs_7d}
                caption={`${t.checks_7d} flock checks this week`}
                captionColor="var(--color-muted)"
                Icon={Activity}
                iconColor="#2F9E58"
              />
            </CardLink>
            <CardLink to="/admin/orgs?status=paying&sort=revenue">
              <StatCard
                label="MRR"
                value={ghs(t.mrr_ghs)}
                caption={`${t.paying_orgs} paying org${t.paying_orgs === 1 ? '' : 's'}`}
                captionColor="var(--color-muted)"
                Icon={Banknote}
                iconColor="#B3811A"
              />
            </CardLink>
            <CardLink to="/admin/orgs?sort=houses">
              <StatCard
                label="Houses monitored"
                value={t.houses}
                caption={`across ${t.farms} farm${t.farms === 1 ? '' : 's'}`}
                captionColor="var(--color-muted)"
                Icon={Warehouse}
              />
            </CardLink>
            <CardLink to="/admin/ai-usage">
              <StatCard
                label="AI requests (month)"
                value={t.ai_requests_month.toLocaleString()}
                Icon={Sparkles}
                iconColor="#6C63D6"
              />
            </CardLink>
            <CardLink to="/admin/orgs?status=alerts&sort=alerts">
              <StatCard
                label="Open alerts"
                value={t.open_alerts}
                caption={t.critical_open_alerts ? `${t.critical_open_alerts} critical` : 'none critical'}
                captionColor={t.critical_open_alerts ? 'var(--color-critical)' : 'var(--color-muted)'}
                Icon={ShieldAlert}
                iconColor="#C8433A"
              />
            </CardLink>
            <CardLink to="/admin/users">
              <StatCard label="Active users" value={t.members} Icon={Users} />
            </CardLink>
            <CardLink to="/admin/orgs?status=inactive">
              <StatCard
                label="Activation"
                value={t.organizations ? `${Math.round((t.active_orgs_7d / t.organizations) * 100)}%` : '—'}
                caption="orgs active this week"
                captionColor="var(--color-muted)"
                Icon={Activity}
              />
            </CardLink>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Flock checks per day (last 14 days)">
              <CountBars
                data={data.checks_by_day}
                xKey="day"
                noun="checks"
                color="var(--color-series-1)"
                tickFormatter={dayLabel}
              />
            </Card>
            <Card title="New organizations per month">
              <CountBars
                data={data.signups_by_month}
                xKey="month"
                noun="new orgs"
                color="var(--color-series-3)"
                tickFormatter={monthLabel}
              />
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="Plans">
              <ul className="space-y-2">
                {planRows.map(([plan, count]) => (
                  <li key={plan}>
                    <Link
                      to={`/admin/orgs?plan=${plan}`}
                      className="-mx-2 flex items-center justify-between rounded-lg px-2 py-1 text-sm hover:bg-forest/5"
                    >
                      <PlanBadge plan={plan} />
                      <span className="font-semibold tabular-nums text-navy">
                        {count}
                        <span className="ml-1 text-xs font-normal text-muted">
                          ({Math.round((count / t.organizations) * 100)}%)
                        </span>
                      </span>
                    </Link>
                  </li>
                ))}
                {planRows.length === 0 ? <li className="text-sm text-muted">No organizations yet.</li> : null}
              </ul>
            </Card>

            <Card
              title="Near their limits (upgrade leads)"
              className="lg:col-span-2"
              action={<span className="text-xs text-muted">≥ 80% of AI requests or houses</span>}
            >
              {data.near_limit.length === 0 ? (
                <p className="text-sm text-muted">No organization is close to a plan limit.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-xs text-muted">
                        <th className="pb-2 font-semibold">Organization</th>
                        <th className="pb-2 font-semibold">Plan</th>
                        <th className="pb-2 font-semibold">AI requests</th>
                        <th className="pb-2 font-semibold">Houses</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-hairline">
                      {data.near_limit.map((o) => (
                        <tr key={o.org_id}>
                          <td className="py-2 pr-3">
                            <Link to={`/admin/orgs/${o.org_id}`} className="font-semibold text-navy hover:text-forest">
                              {o.farms[0]?.name || o.owner_email || o.org_id}
                            </Link>
                          </td>
                          <td className="py-2 pr-3">
                            <PlanBadge plan={o.plan} comped={o.comped} />
                          </td>
                          <td className="py-2 pr-3">
                            <UsageBar ratio={o.ai_usage_ratio} />
                          </td>
                          <td className="py-2">
                            <UsageBar ratio={o.house_usage_ratio} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          </div>

          <Card
            title="Newest organizations"
            action={
              <Link to="/admin/orgs" className="text-xs font-bold text-forest">
                View all
              </Link>
            }
          >
            <ul className="divide-y divide-hairline">
              {data.recent_signups.map((o) => (
                <li key={o.org_id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                  <Link to={`/admin/orgs/${o.org_id}`} className="min-w-0">
                    <span className="block truncate text-sm font-semibold text-navy hover:text-forest">
                      {o.farms[0]?.name || 'No farm yet'}
                    </span>
                    <span className="block truncate text-xs text-muted">{o.owner_email || o.org_id}</span>
                  </Link>
                  <div className="flex items-center gap-3 text-xs text-muted">
                    <PlanBadge plan={o.plan} comped={o.comped} />
                    <span>Joined {shortDate(o.created_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
          <p className="text-xs text-muted">MRR counts active, paid, non-comped, non-suspended subscriptions.</p>
        </>
      ) : null}
    </div>
  )
}
