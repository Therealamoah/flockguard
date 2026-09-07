import LogoMark from './Logo'

export function IconField({ icon: Icon, ...props }) {
  return (
    <div className="relative">
      <Icon size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-navy/40" />
      <input
        {...props}
        className="w-full rounded-lg border border-hairline py-2.5 pl-10 pr-3 text-sm outline-none focus:border-forest"
      />
    </div>
  )
}

export default function AuthShell({ title, subtitle, children, footer }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-linear-to-br from-forest-dark to-forest px-4 py-10">
      <div className="w-full max-w-md rounded-2xl bg-surface p-8 shadow-xl">
        <div className="mb-6 flex items-center justify-center gap-2">
          <LogoMark size={32} />
          <span className="font-display text-xl font-extrabold text-navy">FlockGuard</span>
        </div>

        <h1 className="text-center font-display text-2xl font-extrabold text-navy">{title}</h1>
        {subtitle ? <p className="mt-1 text-center text-sm text-navy/60">{subtitle}</p> : null}

        <div className="mt-6">{children}</div>

        {footer ? <p className="mt-6 text-center text-sm text-navy/70">{footer}</p> : null}
      </div>
    </div>
  )
}
