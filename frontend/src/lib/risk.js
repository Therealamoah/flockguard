// Mirrors backend/app/risk_engine/status.py - keep thresholds in sync.
export const STATUS_META = {
  normal: { label: 'Normal', color: '#2F9E58', range: '0–24' },
  watch: { label: 'Watch', color: '#B3811A', range: '25–49' },
  warning: { label: 'Warning', color: '#C05A1D', range: '50–74' },
  critical: { label: 'Critical', color: '#C8433A', range: '75–100' },
}

export function statusFromScore(score) {
  if (score <= 24) return 'normal'
  if (score <= 49) return 'watch'
  if (score <= 74) return 'warning'
  return 'critical'
}

export function statusMeta(status) {
  return STATUS_META[status] || STATUS_META.normal
}
