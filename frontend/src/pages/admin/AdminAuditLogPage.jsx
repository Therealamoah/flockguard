import { Fragment, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronDown, ChevronRight, ScrollText } from 'lucide-react'
import { api } from '../../lib/api'
import { ErrorBlock, LoadingBlock, PageHeader } from '../../components/admin/AdminUI'
import { dateTime } from '../../lib/adminFormat'
import { useAdminData } from '../../lib/useAdminData'

const ACTION_LABEL = {
  'subscription.override': 'Changed plan',
  'org.suspend': 'Suspended org',
  'org.reactivate': 'Reactivated org',
  'user.disable': 'Disabled user',
  'user.enable': 'Enabled user',
}

const ACTION_COLOR = {
  'org.suspend': 'text-critical',
  'user.disable': 'text-critical',
  'org.reactivate': 'text-normal',
  'user.enable': 'text-normal',
}

const loadAuditLog = () => api.admin.auditLog({ limit: 200 })

export default function AdminAuditLogPage() {
  const { data, error, isLoading, reload } = useAdminData(loadAuditLog)
  const [openId, setOpenId] = useState(null)

  return (
    <div className="mx-auto max-w-5xl space-y-4 p-4 lg:p-6">
      <PageHeader
        Icon={ScrollText}
        title="Audit log"
        subtitle="Every change a platform admin has made, newest first."
      />

      {error ? <ErrorBlock message={error} onRetry={reload} /> : null}
      {!data && isLoading ? <LoadingBlock /> : null}

      {data ? (
        <div className="overflow-x-auto rounded-xl border border-hairline bg-surface shadow-sm">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="border-b border-hairline text-left text-xs text-muted">
              <tr>
                <th className="w-8 px-3 py-3" />
                <th className="px-3 py-3 font-semibold">When</th>
                <th className="px-3 py-3 font-semibold">Action</th>
                <th className="px-3 py-3 font-semibold">Admin</th>
                <th className="px-3 py-3 font-semibold">Target</th>
                <th className="px-4 py-3 font-semibold">Reason</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-hairline">
              {data.map((e) => (
                <Fragment key={e.id}>
                  <tr
                    className="cursor-pointer hover:bg-forest/5"
                    onClick={() => setOpenId(openId === e.id ? null : e.id)}
                  >
                    <td className="px-3 py-3 text-muted">
                      {openId === e.id ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-xs text-secondary">{dateTime(e.created_at)}</td>
                    <td className={`px-3 py-3 font-semibold ${ACTION_COLOR[e.action] || 'text-navy'}`}>
                      {ACTION_LABEL[e.action] || e.action}
                    </td>
                    <td className="px-3 py-3 text-xs text-secondary">{e.admin_email || e.admin_uid}</td>
                    <td className="px-3 py-3 text-xs">
                      {e.org_id ? (
                        <Link
                          to={`/admin/orgs/${e.org_id}`}
                          onClick={(ev) => ev.stopPropagation()}
                          className="font-bold text-forest hover:underline"
                        >
                          {e.target_uid ? `user ${e.target_uid.slice(0, 8)}…` : `org ${e.org_id.slice(0, 8)}…`}
                        </Link>
                      ) : (
                        <span className="text-muted">{e.target_uid || '—'}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-secondary">{e.reason}</td>
                  </tr>
                  {openId === e.id ? (
                    <tr>
                      <td />
                      <td colSpan={5} className="px-3 pb-4">
                        <div className="grid gap-3 md:grid-cols-2">
                          {['before', 'after'].map((k) => (
                            <div key={k}>
                              <p className="mb-1 text-xs font-bold uppercase text-muted">{k}</p>
                              <pre className="overflow-x-auto rounded-lg bg-bg p-3 text-xs text-navy">
                                {JSON.stringify(e[k], null, 2)}
                              </pre>
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              ))}
              {data.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-sm text-muted">
                    No admin actions yet.
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
