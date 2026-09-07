export function displayName(user) {
  if (!user) return 'there'
  if (user.displayName) return user.displayName
  const local = (user.email || '').split('@')[0]
  return local
    .split(/[._-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export function dayLabel(startDate) {
  if (!startDate) return null
  const days = Math.floor((Date.now() - new Date(startDate).getTime()) / 86400000) + 1
  return `Day ${Math.max(days, 1)}`
}

export function weekLabel(startDate) {
  if (!startDate) return null
  const days = Math.floor((Date.now() - new Date(startDate).getTime()) / 86400000) + 1
  return `Week ${Math.max(Math.ceil(days / 7), 1)}`
}

// Layers are kept for a full production cycle (often a year+), so age reads
// more usefully in weeks; broilers/breeders are short-cycle, so days.
export function ageLabel(flock) {
  if (!flock?.start_date) return null
  return flock.bird_type === 'layer' ? weekLabel(flock.start_date) : dayLabel(flock.start_date)
}

// Deterministic, derived from real flock data (start_date order) - not a
// random or fabricated code. BR-001, LY-001, BE-001, ... per bird type.
const FLOCK_CODE_PREFIX = { broiler: 'BR', layer: 'LY', breeder: 'BE' }

export function assignFlockCodes(flocks) {
  const sorted = [...flocks].sort((a, b) => new Date(a.start_date) - new Date(b.start_date))
  const counters = {}
  const codeById = {}
  for (const flock of sorted) {
    const prefix = FLOCK_CODE_PREFIX[flock.bird_type] || 'FL'
    counters[prefix] = (counters[prefix] || 0) + 1
    codeById[flock.id] = `${prefix}-${String(counters[prefix]).padStart(3, '0')}`
  }
  return codeById
}

export function initialsFor(user) {
  const name = displayName(user)
  const parts = name.split(' ').filter(Boolean)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return name.slice(0, 2).toUpperCase()
}
