import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { Activity, CalendarDays, CalendarRange, Moon, Radio, RefreshCw, Repeat, Users } from 'lucide-react'
import StatCard from '../../components/StatCard'
import { api } from '../../lib/api'
import { timeAgo } from '../../lib/time'
import { Card, CountBars, ErrorBlock, LoadingBlock, PageHeader } from '../../components/admin/AdminUI'
import { dayLabel, pct, shortDate } from '../../lib/adminFormat'
import { useAdminData } from '../../lib/useAdminData'

const REFRESH_MS = 30_000

function Person({ p }) {
  return (
    <>
      <span className="block truncate font-semibold text-navy">{p.display_name || p.email || p.uid}</span>
      {p.display_name && p.email ? <span className="block truncate text-xs text-muted">{p.email}</span> : null}
    </>
  )
}

function OrgLink({ p }) {
  return (
    <Link to={`/admin/orgs/${p.org_id}`} className="text-xs font-semibold text-forest hover:underline">
      {p.farm_name || 'Open org'}
    </Link>
  )
}

function LiveDot() {
  return (
    <span className="relative flex h-2.5 w-2.5">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-normal opacity-60" />
      <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-normal" />
    </span>
  )
}

function Empty({ children }) {
  return <p className="py-6 text-center text-sm text-muted">{children}</p>
}

export default function AdminActivityPage() {
  const { data, error, isLoading, reload } = useAdminData(api.admin.activity)

  // "Online now" is only useful if it stays current.
  useEffect(() => {
    const id = setInterval(() => {
      if (document.visibilityState === 'visible') reload()
    }, REFRESH_MS)
    return () => clearInterval(id)
  }, [reload])

  const t = data?.totals

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 lg:p-6">
      <PageHeader Icon={Activity} title="Activity" subtitle="Who is using FlockGuard - live, and over the last 30 days.">
        <div className="flex items-center gap-3">
          {data ? <span className="text-xs text-muted">Updated {timeAgo(data.generated_at)} · auto-refreshes</span> : null}
          <button
            onClick={reload}
            className="flex items-center gap-1.5 rounded-lg border border-hairline bg-surface px-3 py-2 text-sm font-semibold text-secondary hover:text-navy"
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </PageHeader>

      {error ? <ErrorBlock message={error} onRetry={reload} /> : null}
      {!data && isLoading ? <LoadingBlock /> : null}

      {t ? (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
            <StatCard
              label="Online now"
              value={t.online_now}
              caption={`active in the last ${data.online_window_minutes} min`}
              captionColor="var(--color-muted)"
              Icon={Radio}
              iconColor="#2F9E58"
            />
            <StatCard label="Today (DAU)" value={t.dau} caption="since 00:00 UTC" captionColor="var(--color-muted)" Icon={Users} />
            <StatCard label="This week (WAU)" value={t.wau} caption="last 7 days" captionColor="var(--color-muted)" Icon={CalendarDays} />
            <StatCard label="This month (MAU)" value={t.mau} caption="last 30 days" captionColor="var(--color-muted)" Icon={CalendarRange} />
            <StatCard
              label="Stickiness"
              value={pct(t.stickiness)}
              caption="DAU ÷ MAU"
              captionColor="var(--color-muted)"
              Icon={Repeat}
              iconColor="#6C63D6"
            />
          </div>

          <Card title="Active users per day (last 30 days)">
            <CountBars data={data.dau_by_day} xKey="day" noun="active users" color="var(--color-series-1)" tickFormatter={dayLabel} />
          </Card>

          <Card
            title={
              <span className="flex items-center gap-2">
                {t.online_now ? <LiveDot /> : null}
                Online now ({t.online_now})
              </span>
            }
          >
            {data.online.length === 0 ? (
              <Empty>Nobody is using the app right now.</Empty>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[560px] text-sm">
                  <thead className="text-left text-xs text-muted">
                    <tr>
                      <th className="pb-2 font-semibold">Person</th>
                      <th className="pb-2 font-semibold">Farm</th>
                      <th className="pb-2 font-semibold">On page</th>
                      <th className="pb-2 font-semibold">Last seen</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-hairline">
                    {data.online.map((p) => (
                      <tr key={p.uid}>
                        <td className="max-w-[220px] py-2.5 pr-3"><Person p={p} /></td>
                        <td className="py-2.5 pr-3"><OrgLink p={p} /></td>
                        <td className="py-2.5 pr-3 font-mono text-xs text-secondary">{p.last_path || '—'}</td>
                        <td className="py-2.5 text-xs text-secondary">{timeAgo(p.last_seen_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Recently active" action={<span className="text-xs text-muted">latest 50</span>}>
              {data.recent.length === 0 ? (
                <Empty>No activity recorded yet. It starts as soon as people open the updated app.</Empty>
              ) : (
                <ul className="divide-y divide-hairline">
                  {data.recent.map((p) => (
                    <li key={p.uid} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                      <div className="min-w-0">
                        <Person p={p} />
                        <OrgLink p={p} />
                      </div>
                      <div className="shrink-0 text-right text-xs">
                        <span className="block font-semibold text-navy">{timeAgo(p.last_seen_at)}</span>
                        <span className="block text-muted">
                          {p.days_active_30d} day{p.days_active_30d === 1 ? '' : 's'} active / 30
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card
              title={
                <span className="flex items-center gap-2">
                  <Moon size={14} className="text-muted" />
                  Dormant ({t.dormant})
                </span>
              }
              action={<span className="text-xs text-muted">no visit in {data.dormant_after_days}+ days</span>}
            >
              {data.dormant.length === 0 ? (
                <Empty>Everyone has been active recently.</Empty>
              ) : (
                <ul className="divide-y divide-hairline">
                  {data.dormant.map((p) => (
                    <li key={`${p.org_id}-${p.uid}`} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                      <div className="min-w-0">
                        <Person p={p} />
                        <OrgLink p={p} />
                      </div>
                      <div className="shrink-0 text-right text-xs text-muted">
                        <span className="block">{p.last_seen_at ? `last seen ${timeAgo(p.last_seen_at)}` : 'never seen'}</span>
                        <span className="block capitalize">
                          {p.role} · joined {shortDate(p.joined_at)}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <p className="text-xs text-muted">
            Someone counts as active when they have the farm app open in a visible tab. Tracking started when this
            feature shipped, so earlier activity isn't counted - "never seen" users may simply not have visited since.
          </p>
        </>
      ) : null}
    </div>
  )
}
