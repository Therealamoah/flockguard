import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Bot, Sparkles, TriangleAlert } from 'lucide-react'
import StatCard from '../../components/StatCard'
import { api } from '../../lib/api'
import { Card, ErrorBlock, LoadingBlock, PageHeader, PlanBadge, UsageBar } from '../../components/admin/AdminUI'
import { useAdminData } from '../../lib/useAdminData'

const axisProps = { tick: { fill: 'var(--color-muted)', fontSize: 11 }, tickLine: false, axisLine: false }
const monthLabel = (p) => new Date(`${p}-01T00:00:00`).toLocaleDateString([], { month: 'short', year: '2-digit' })

function Breakdown({ counts, empty }) {
  const rows = Object.entries(counts).sort((a, b) => b[1] - a[1])
  const total = rows.reduce((sum, [, n]) => sum + n, 0)
  if (!rows.length) return <p className="text-sm text-muted">{empty}</p>
  return (
    <ul className="space-y-2.5">
      {rows.map(([label, n]) => (
        <li key={label}>
          <div className="flex justify-between text-sm">
            <span className="text-navy">{label}</span>
            <span className="font-semibold tabular-nums text-secondary">{n}</span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-hairline">
            <div className="h-full rounded-full bg-ai" style={{ width: `${(n / total) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

export default function AdminAiUsagePage() {
  const { data, error, isLoading, reload } = useAdminData(api.admin.aiUsage)

  const totalRuns = data ? Object.values(data.agent_runs_by_status).reduce((a, b) => a + b, 0) : 0
  const failedRuns = data ? totalRuns - (data.agent_runs_by_status.completed || 0) : 0
  const overLimit = data ? data.orgs.filter((o) => (o.ai_usage_ratio || 0) >= 1).length : 0

  return (
    <div className="mx-auto max-w-6xl space-y-5 p-4 lg:p-6">
      <PageHeader
        Icon={Sparkles}
        title="AI usage"
        subtitle="Ask FlockGuard, photo review and agent investigations, by org."
      />

      {error ? <ErrorBlock message={error} onRetry={reload} /> : null}
      {!data && isLoading ? <LoadingBlock /> : null}

      {data ? (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Requests this month"
              value={data.total_requests_month.toLocaleString()}
              Icon={Sparkles}
              iconColor="#6C63D6"
            />
            <StatCard label="Agent runs this month" value={totalRuns} Icon={Bot} iconColor="#6C63D6" />
            <StatCard
              label="Agent runs not completed"
              value={failedRuns}
              caption={totalRuns ? `${Math.round((failedRuns / totalRuns) * 100)}% of runs` : null}
              captionColor={failedRuns ? 'var(--color-warning)' : 'var(--color-muted)'}
              Icon={TriangleAlert}
              iconColor="#C05A1D"
            />
            <StatCard
              label="Orgs at their AI limit"
              value={overLimit}
              captionColor="var(--color-muted)"
              caption="blocked until next month or upgrade"
              Icon={TriangleAlert}
              iconColor="#C8433A"
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card title="AI requests per month" className="lg:col-span-1">
              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.requests_by_period} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="var(--color-hairline)" strokeDasharray="3 3" />
                    <XAxis dataKey="period" tickFormatter={monthLabel} {...axisProps} />
                    <YAxis width={36} allowDecimals={false} {...axisProps} />
                    <Tooltip
                      cursor={{ fill: 'var(--color-hairline)', opacity: 0.4 }}
                      contentStyle={{
                        background: 'var(--color-surface)',
                        border: '1px solid var(--color-hairline)',
                        borderRadius: 8,
                        fontSize: 12,
                      }}
                      labelFormatter={monthLabel}
                      formatter={(v) => [v, 'requests']}
                    />
                    <Bar dataKey="count" fill="var(--color-ai)" radius={[4, 4, 0, 0]} maxBarSize={28} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card title="Agent runs by skill">
              <Breakdown counts={data.agent_runs_by_skill} empty="No agent runs this month." />
            </Card>
            <Card title="Agent runs by outcome">
              <Breakdown counts={data.agent_runs_by_status} empty="No agent runs this month." />
            </Card>
          </div>

          <Card title={`By organization · ${data.period}`}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[600px] text-sm">
                <thead className="text-left text-xs text-muted">
                  <tr>
                    <th className="pb-2 font-semibold">Organization</th>
                    <th className="pb-2 font-semibold">Plan</th>
                    <th className="pb-2 font-semibold">Requests</th>
                    <th className="pb-2 font-semibold">Of limit</th>
                    <th className="pb-2 font-semibold">Agent runs</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline">
                  {data.orgs.map((o) => (
                    <tr key={o.org_id}>
                      <td className="py-2.5 pr-3">
                        <Link to={`/admin/orgs/${o.org_id}`} className="font-semibold text-navy hover:text-forest">
                          {o.farm_name || o.owner_email || o.org_id}
                        </Link>
                      </td>
                      <td className="py-2.5 pr-3">
                        <PlanBadge plan={o.plan} />
                      </td>
                      <td className="py-2.5 pr-3 tabular-nums text-secondary">
                        {o.ai_requests_month} <span className="text-xs text-muted">/ {o.ai_limit ?? '∞'}</span>
                      </td>
                      <td className="py-2.5 pr-3">
                        <UsageBar ratio={o.ai_usage_ratio} />
                      </td>
                      <td className="py-2.5 tabular-nums text-secondary">{o.agent_runs_month}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      ) : null}
    </div>
  )
}
