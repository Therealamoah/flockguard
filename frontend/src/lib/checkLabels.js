// Plain farm words for Flock Check values. The keys match the backend
// enums (app/risk_engine/models.py); the labels are what farmers see - no
// "lethargic", "mortality" or "consumption" anywhere in the UI.
export const WATER_LABELS = { normal: 'Same as usual', lower: 'Less than usual', higher: 'More than usual' }
export const ACTIVITY_LABELS = { normal: 'Active', reduced: 'Less active', lethargic: 'Weak / dull' }
export const FEEDING_LABELS = { normal: 'Eating well', reduced: 'Eating less', none: 'Not eating' }
export const PERIOD_LABELS = { morning: 'Morning', evening: 'Evening', emergency: 'Emergency' }

// Risk Engine factor keys (backend/app/risk_engine/engine.py) in a FIXED
// order - charts color each one by this position (--color-series-N), never
// by rank, so "Huddling together" is the same color on every chart.
export const FACTOR_ORDER = [
  'mortality',
  'sick_or_injured',
  'activity',
  'feeding_behaviour',
  'feed',
  'water',
  'crowding',
  'sound',
]
export const FACTOR_LABELS = {
  mortality: 'Birds dying',
  sick_or_injured: 'Sick or hurt birds',
  activity: 'Less active / weak',
  feeding_behaviour: 'Eating less',
  feed: 'Less feed eaten',
  water: 'Drinking less water',
  crowding: 'Huddling together',
  sound: 'Coughing / strange sounds',
}
