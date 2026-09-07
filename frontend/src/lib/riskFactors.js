// Deterministic inspection guidance keyed to the Risk Engine's own factor
// keys (backend/app/risk_engine/engine.py). No AI involved - the Risk
// Engine already found the pattern, this just tells the farmer where to
// look first and why. Never a disease diagnosis.
const SUGGESTIONS = {
  mortality: {
    headline: 'Inspect for early signs of illness or injury',
    detail: 'Given the mortality uptick.',
  },
  feed: {
    headline: 'Check feeder lines and feed quality',
    detail: 'Most likely cause of the feed dip.',
  },
  water: {
    headline: 'Check water lines and nipples/drinkers',
    detail: 'Water intake dropped this check.',
  },
  activity: {
    headline: 'Observe bird movement and posture closely',
    detail: 'Reduced activity was reported.',
  },
  feeding_behaviour: {
    headline: 'Watch feeding time closely',
    detail: 'Birds may be avoiding feeders.',
  },
  crowding: {
    headline: 'Check stocking density and ventilation',
    detail: 'Crowding was observed.',
  },
  sound: {
    headline: 'Listen for respiratory distress',
    detail: 'Unusual noise was reported.',
  },
  sick_or_injured: {
    headline: 'Isolate and examine affected birds',
    detail: 'Sick or injured birds were observed.',
  },
}

export function inspectionPriorities(factors, limit = 3) {
  return [...factors]
    .sort((a, b) => b.points - a.points)
    .slice(0, limit)
    .map((f) => ({
      key: f.key,
      ...(SUGGESTIONS[f.key] || { headline: 'Inspect this house closely', detail: f.label }),
    }))
}
