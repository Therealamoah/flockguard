export default function StatCard({ label, value, caption, captionColor, Icon, iconColor = '#1B4332' }) {
  return (
    <div className="rounded-lg border border-hairline bg-surface p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-navy/50">{label}</p>
        {Icon ? (
          <span
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
            style={{ backgroundColor: `${iconColor}1A`, color: iconColor }}
          >
            <Icon size={15} />
          </span>
        ) : null}
      </div>
      <p className="mt-2 font-display text-2xl font-extrabold text-navy">{value}</p>
      {caption ? (
        <p className="mt-0.5 text-xs font-medium" style={{ color: captionColor }}>
          {caption}
        </p>
      ) : null}
    </div>
  )
}
