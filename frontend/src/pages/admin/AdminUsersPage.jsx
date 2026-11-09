import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Users } from 'lucide-react'
import { api } from '../../lib/api'
import { ErrorBlock, LoadingBlock, PageHeader } from '../../components/admin/AdminUI'
import { shortDate } from '../../lib/adminFormat'
import { timeAgo } from '../../lib/time'
import { useAdminData } from '../../lib/useAdminData'

export default function AdminUsersPage() {
  const [input, setInput] = useState('')
  const [query, setQuery] = useState('')

  useEffect(() => {
    const id = setTimeout(() => setQuery(input.trim()), 300)
    return () => clearTimeout(id)
  }, [input])

  const { data, error, isLoading, reload } = useAdminData(api.admin.users, query)

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4 lg:p-6">
      <PageHeader Icon={Users} title="Users" subtitle="Find anyone by email, name or UID, in any organization." />

      <div className="relative">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
        <input
          autoFocus
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Search users..."
          className="w-full rounded-lg border border-hairline bg-surface py-2.5 pl-9 pr-3 text-sm text-navy outline-none focus:border-forest"
        />
      </div>

      {error ? <ErrorBlock message={error} onRetry={reload} /> : null}
      {!data && isLoading ? <LoadingBlock /> : null}

      {data ? (
        <div className="overflow-x-auto rounded-xl border border-hairline bg-surface shadow-sm">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="border-b border-hairline text-left text-xs text-muted">
              <tr>
                <th className="px-4 py-3 font-semibold">Person</th>
                <th className="px-3 py-3 font-semibold">Role</th>
                <th className="px-3 py-3 font-semibold">Membership</th>
                <th className="px-3 py-3 font-semibold">Last active</th>
                <th className="px-3 py-3 font-semibold">Joined</th>
                <th className="px-4 py-3 font-semibold">Organization</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline">
              {data.map((u) => (
                <tr key={`${u.org_id}-${u.uid}`}>
                  <td className="px-4 py-3">
                    <span className="block font-semibold text-navy">{u.display_name || u.email}</span>
                    <span className="block text-xs text-muted">{u.email}</span>
                  </td>
                  <td className="px-3 py-3 capitalize text-secondary">{u.role}</td>
                  <td className="px-3 py-3 capitalize text-secondary">{u.status}</td>
                  <td className="px-3 py-3 text-xs">
                    <span className="block font-semibold text-navy">{timeAgo(u.last_seen_at) || 'never'}</span>
                    <span className="block text-muted">{u.days_active_30d} days / 30</span>
                  </td>
                  <td className="px-3 py-3 text-xs text-secondary">{shortDate(u.joined_at)}</td>
                  <td className="px-4 py-3">
                    <Link to={`/admin/orgs/${u.org_id}`} className="text-xs font-bold text-forest hover:underline">
                      Open org →
                    </Link>
                  </td>
                </tr>
              ))}
              {data.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-sm text-muted">
                    No users match “{query}”.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
          {data.length === 200 ? (
            <p className="border-t border-hairline px-4 py-2 text-xs text-muted">
              Showing the first 200 - narrow your search.
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
