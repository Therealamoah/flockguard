import { useState } from 'react'
import { CheckCircle2, CircleAlert, CircleOff, Mail, MailCheck, Send, Server, Users } from 'lucide-react'
import { api } from '../../lib/api'
import { Card, ErrorBlock, LoadingBlock, PageHeader } from '../../components/admin/AdminUI'
import { useAdminData } from '../../lib/useAdminData'

const STATUS = {
  on: { label: 'Sending', Icon: CheckCircle2, className: 'bg-normal/10 text-normal' },
  limited: { label: 'Needs farmers to opt in', Icon: CircleAlert, className: 'bg-warning/10 text-warning' },
  off: { label: 'Not sending', Icon: CircleOff, className: 'bg-critical/10 text-critical' },
}

function StatusPill({ status }) {
  const { label, Icon, className } = STATUS[status] || STATUS.off
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-bold ${className}`}>
      <Icon size={12} />
      {label}
    </span>
  )
}

function DeliveryCard({ delivery, alertFarms }) {
  return (
    <Card title="How email is sent">
      <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-xs font-semibold text-muted">Provider</dt>
          <dd className="mt-0.5 flex items-center gap-1.5 font-semibold text-navy">
            <Server size={14} />
            {delivery.configured ? `${delivery.provider} (${delivery.host}:${delivery.port})` : 'Not configured'}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-semibold text-muted">Sent from</dt>
          <dd className="mt-0.5 break-all font-semibold text-navy">
            {delivery.from_name} &lt;{delivery.from_email || '—'}&gt;
          </dd>
        </div>
        <div>
          <dt className="text-xs font-semibold text-muted">Farms with email alerts on</dt>
          <dd className="mt-0.5 font-semibold text-navy">
            {alertFarms.enabled} of {alertFarms.total}
          </dd>
        </div>
        <div>
          <dt className="text-xs font-semibold text-muted">Enterprise requests go to</dt>
          <dd className="mt-0.5 break-all font-semibold text-navy">{delivery.sales_notification_email || 'Not set'}</dd>
        </div>
      </dl>
      <p className="mt-3 text-xs text-muted">
        Delivery history (sent, delivered, bounced, spam) is in your provider's logs - for Brevo: Transactional → Logs.
      </p>
    </Card>
  )
}

function TemplateCard({ template, isOpen, onToggle }) {
  const [view, setView] = useState('html')
  const [testState, setTestState] = useState({ status: 'idle', text: '' })

  async function sendTest() {
    setTestState({ status: 'sending', text: '' })
    try {
      const { to } = await api.admin.sendTestEmail(template.key)
      setTestState({ status: 'sent', text: `Sent to ${to} - check your inbox (and spam).` })
    } catch (err) {
      setTestState({ status: 'error', text: err.detail || 'Could not send the test email.' })
    }
  }

  return (
    <section className="overflow-hidden rounded-xl border border-hairline bg-surface shadow-sm">
      <button onClick={onToggle} className="flex w-full flex-wrap items-start gap-3 p-4 text-left hover:bg-forest/5">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-forest/10 text-forest">
          <Mail size={17} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="font-bold text-navy">{template.name}</h2>
            <StatusPill status={template.status} />
          </div>
          <p className="mt-0.5 truncate text-sm text-secondary">
            <span className="text-muted">Subject:</span> {template.subject}
          </p>
        </div>
        <span className="text-xs font-bold text-forest">{isOpen ? 'Hide' : 'Preview'}</span>
      </button>

      {isOpen ? (
        <div className="space-y-4 border-t border-hairline p-4">
          <div className="grid gap-3 text-sm md:grid-cols-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted">When</p>
              <p className="mt-1 text-secondary">{template.trigger}</p>
            </div>
            <div>
              <p className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wide text-muted">
                <Users size={12} /> Who gets it
              </p>
              <p className="mt-1 text-secondary">{template.audience}</p>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted">Right now</p>
              <p className="mt-1 text-secondary">{template.status_note}</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex gap-1 rounded-lg bg-bg p-1">
              {[
                ['html', 'Email'],
                ['text', 'Plain text'],
              ].map(([value, label]) => (
                <button
                  key={value}
                  onClick={() => setView(value)}
                  className={`rounded-md px-3 py-1 text-xs font-semibold ${
                    view === value ? 'bg-surface text-navy shadow-sm' : 'text-secondary hover:text-navy'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <button
              onClick={sendTest}
              disabled={testState.status === 'sending'}
              className="flex items-center gap-1.5 rounded-lg bg-forest px-3 py-2 text-xs font-bold text-white hover:bg-forest-dark disabled:opacity-60"
            >
              <Send size={13} />
              {testState.status === 'sending' ? 'Sending...' : 'Send me a test'}
            </button>
          </div>
          {testState.text ? (
            <p
              className={`flex items-center gap-1.5 text-sm ${testState.status === 'error' ? 'text-critical' : 'text-normal'}`}
            >
              {testState.status === 'error' ? <CircleAlert size={14} /> : <MailCheck size={14} />}
              {testState.text}
            </p>
          ) : null}

          {view === 'html' ? (
            // Rendered in a sandboxed iframe: email HTML carries its own
            // styles, and sandboxing keeps it from running anything here.
            <iframe
              title={`${template.name} preview`}
              sandbox=""
              srcDoc={template.html_body}
              className="h-[560px] w-full rounded-lg border border-hairline bg-white"
            />
          ) : (
            <pre className="max-h-[560px] overflow-auto whitespace-pre-wrap rounded-lg border border-hairline bg-bg p-4 text-xs text-navy">
              {template.text_body}
            </pre>
          )}
          <p className="text-xs text-muted">Preview uses sample names and numbers; real emails use the farm's own details.</p>
        </div>
      ) : null}
    </section>
  )
}

export default function AdminEmailsPage() {
  const { data, error, isLoading, reload } = useAdminData(api.admin.emails)
  const [openKey, setOpenKey] = useState(null)

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-4 lg:p-6">
      <PageHeader Icon={Mail} title="Emails" subtitle="Every email FlockGuard sends, who gets it, and exactly what it looks like." />

      {error ? <ErrorBlock message={error} onRetry={reload} /> : null}
      {!data && isLoading ? <LoadingBlock /> : null}

      {data ? (
        <>
          <DeliveryCard delivery={data.delivery} alertFarms={data.alert_email_farms} />
          <div className="space-y-3">
            {data.templates.map((t) => (
              <TemplateCard
                key={t.key}
                template={t}
                isOpen={openKey === t.key}
                onToggle={() => setOpenKey(openKey === t.key ? null : t.key)}
              />
            ))}
          </div>
        </>
      ) : null}
    </div>
  )
}
