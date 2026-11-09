import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Building2, Search } from 'lucide-react'
import { api } from '../../lib/api'
import { timeAgo } from '../../lib/time'
import {
  ErrorBlock,
  LoadingBlock,
  OrgStatusBadge,
  PageHeader,
  PlanBadge,
  UsageBar,
} from '../../components/admin/AdminUI'
import { PLAN_LABEL, shortDate } from '../../lib/adminFormat'
import { useAdminData } from '../../lib/useAdminData'

const SORTS = {
  newest: { label: 'Newest', fn: (a, b) => (b.created_at || '').localeCompare(a.created_at || '') },
  activity: { label: 'Last activity', fn: (a, b) => (b.last_check_at || '').localeCompare(a.last_check_at || '') },
  ai: { label: 'AI usage', fn: (a, b) => b.ai_requests_month - a.ai_requests_month },
  alerts: { label: 'Open alerts', fn: (a, b) => b.open_alerts - a.open_alerts },
  houses: { label: 'Houses', fn: (a, b) => b.houses - a.houses },
  revenue: { label: 'Revenue', fn: (a, b) => (b.paying ? b.price_ghs : 0) - (a.paying ? a.price_ghs : 0) },
}

const STATUS_FILTERS = {
  active: (o) => o.platform_status === 'active',
  inactive: (o) => o.checks_7d === 0,
  paying: (o) => o.paying,
  alerts: (o) => o.open_alerts > 0,
  suspended: (o) => o.platform_status === 'suspended',
}

export default function AdminOrgsPage() {
  const { data, error, isLoading, reload } = useAdminData(api.admin.orgs)
  // Filters live in the URL so the overview cards can link straight to a
  // filtered view (e.g. /admin/orgs?status=paying) and it survives refresh.
  const [params, setParams] = useSearchParams()
  const query = params.get('q') || ''
  const plan = params.get('plan') || 'all'
  const status = STATUS_FILTERS[params.get('status')] ? params.get('status') : 'all'
  const sort = SORTS[params.get('sort')] ? params.get('sort') : 'newest'

  function setParam(key, value, fallback) {
    const next = new URLSearchParams(params)
    if (!value || value === fallback) next.delete(key)
    else next.set(key, value)
    setParams(next, { replace: true })
  }
  const setQuery = (v) => setParam('q', v, '')
  const setPlan = (v) => setParam('plan', v, 'all')
  const setStatus = (v) => setParam('status', v, 'all')
  const setSort = (v) => setParam('sort', v, 'newest')

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return (data || [])
      .filter((o) => plan === 'all' || o.plan === plan)
      .filter((o) => status === 'all' || STATUS_FILTERS[status](o))
      .filter((o) => {
        if (!needle) return true
        const text = [o.org_id, o.owner_email, o.owner_name, ...o.farms.map((f) => f.name)].join(' ').toLowerCase()
        return text.includes(needle)
      })
      .sort(SORTS[sort].fn)
  }, [data, query, plan, status, sort])

  const selectClass =
    'rounded-lg border border-hairline bg-surface px-3 py-2 text-sm text-navy outline-none focus:border-forest'

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 lg:p-6">
      <PageHeader
        Icon={Building2}
        title="Organizations"
        subtitle={data ? `${rows.length} of ${data.length} shown` : 'Every farm business on FlockGuard.'}
      />

      <div className="flex flex-wrap gap-2">
        <div className="relative min-w-0 flex-1 basis-60">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search farm, owner email, org ID..."
            className="w-full rounded-lg border border-hairline bg-surface py-2 pl-9 pr-3 text-sm text-navy outline-none focus:border-forest"
          />
        </div>
        <select value={plan} onChange={(e) => setPlan(e.target.value)} className={selectClass}>
          <option value="all">All plans</option>
          {Object.entries(PLAN_LABEL).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className={selectClass}>
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="paying">Paying</option>
          <option value="alerts">Has open alerts</option>
          <option value="inactive">No checks in 7 days</option>
          <option value="suspended">Suspended</option>
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} className={selectClass}>
          {Object.entries(SORTS).map(([value, { label }]) => (
            <option key={value} value={value}>
              Sort: {label}
            </option>
          ))}
        </select>
      </div>

      {error ? <ErrorBlock message={error} onRetry={reload} /> : null}
      {!data && isLoading ? <LoadingBlock /> : null}

      {data ? (
        <div className="overflow-x-auto rounded-xl border border-hairline bg-surface shadow-sm">
          <table className="w-full min-w-[820px] text-sm">
            <thead className="border-b border-hairline text-left text-xs text-muted">
              <tr>
                <th className="px-4 py-3 font-semibold">Organization</th>
                <th className="px-3 py-3 font-semibold">Plan</th>
                <th className="px-3 py-3 font-semibold">Users</th>
                <th className="px-3 py-3 font-semibold">Houses</th>
                <th className="px-3 py-3 font-semibold">AI this month</th>
                <th className="px-3 py-3 font-semibold">Open alerts</th>
                <th className="px-3 py-3 font-semibold">Last check</th>
                <th className="px-3 py-3 font-semibold">Joined</th>
                <th className="px-4 py-3 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline">
              {rows.map((o) => (
                <tr key={o.org_id} className="hover:bg-forest/5">
                  <td className="px-4 py-3">
                    <Link to={`/admin/orgs/${o.org_id}`} className="block">
                      <span className="block font-semibold text-navy hover:text-forest">
                        {o.farms[0]?.name || 'No farm yet'}
                      </span>
                      <span className="block text-xs text-muted">{o.owner_email || o.org_id}</span>
                    </Link>
                  </td>
                  <td className="px-3 py-3">
                    <PlanBadge plan={o.plan} comped={o.comped} />
                  </td>
                  <td className="px-3 py-3 tabular-nums text-secondary">
                    {o.members_active}
                    {o.pending_invites ? <span className="text-xs text-muted"> +{o.pending_invites}</span> : null}
                  </td>
                  <td className="px-3 py-3 tabular-nums text-secondary">
                    {o.houses}
                    <span className="text-xs text-muted"> / {o.limits.houses ?? '∞'}</span>
                  </td>
                  <td className="px-3 py-3">
                    <UsageBar ratio={o.ai_usage_ratio} />
                  </td>
                  <td className="px-3 py-3 tabular-nums">
                    {o.critical_open_alerts ? (
                      <span className="font-bold text-critical">{o.open_alerts}</span>
                    ) : (
                      <span className="text-secondary">{o.open_alerts}</span>
                    )}
                  </td>
                  <td className="px-3 py-3 text-xs text-secondary">{timeAgo(o.last_check_at) || 'never'}</td>
                  <td className="px-3 py-3 text-xs text-secondary">{shortDate(o.created_at)}</td>
                  <td className="px-4 py-3">
                    <OrgStatusBadge status={o.platform_status} />
                  </td>
                </tr>
              ))}
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-10 text-center text-sm text-muted">
                    No organizations match these filters.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  )
}
