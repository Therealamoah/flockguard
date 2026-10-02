// Deterministic inspection guidance keyed to the Risk Engine's own factor
// keys (backend/app/risk_engine/engine.py). No AI involved - the Risk
// Engine already found the pattern, this just tells the farmer where to
// look first and why. Never a disease diagnosis.
const SUGGESTIONS = {
  mortality: {
    headline: 'Look closely at the birds for sickness or wounds',
    detail: 'More birds died than usual.',
  },
  feed: {
    headline: 'Check the feeders and the feed',
    detail: 'The birds ate less feed - make sure feeders are full and the feed is not spoilt.',
  },
  water: {
    headline: 'Check the drinkers and water lines',
    detail: 'The birds drank less water - look for blocked or empty drinkers.',
  },
  activity: {
    headline: 'Watch how the birds walk and stand',
    detail: 'The birds are less active than usual.',
  },
  feeding_behaviour: {
    headline: 'Watch the birds at feeding time',
    detail: 'They may be staying away from the feeders.',
  },
  crowding: {
    headline: 'Check if the house is too full, too cold or not airy enough',
    detail: 'The birds were huddling together.',
  },
  sound: {
    headline: 'Listen for coughing, sneezing or noisy breathing',
    detail: 'Strange sounds were heard.',
  },
  sick_or_injured: {
    headline: 'Separate the sick birds and look at them closely',
    detail: 'Sick or hurt birds were seen.',
  },
}

export function inspectionPriorities(factors, limit = 3) {
  return [...factors]
    .sort((a, b) => b.points - a.points)
    .slice(0, limit)
    .map((f) => ({
      key: f.key,
      ...(SUGGESTIONS[f.key] || { headline: 'Look over this house closely', detail: f.label }),
    }))
}
