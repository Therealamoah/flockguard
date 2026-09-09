import { getIdToken } from './firebase'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export async function apiFetch(path, options = {}) {
  const idToken = await getIdToken()
  const isFormData = options.body instanceof FormData

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...(idToken ? { Authorization: `Bearer ${idToken}` } : {}),
      ...options.headers,
    },
  })

  if (!response.ok) {
    const body = await response.text()
    throw new Error(`API ${response.status}: ${body}`)
  }

  if (response.status === 204) return null
  return response.json()
}

const post = (path, data) => apiFetch(path, { method: 'POST', body: JSON.stringify(data) })
const patch = (path, data) => apiFetch(path, { method: 'PATCH', body: JSON.stringify(data) })
const get = (path) => apiFetch(path)

export const api = {
  farms: {
    list: () => get('/farms'),
    create: (data) => post('/farms', data),
  },
  houses: {
    list: (farmId) => get(`/farms/${farmId}/houses`),
    create: (farmId, data) => post(`/farms/${farmId}/houses`, data),
    get: (farmId, houseId) => get(`/farms/${farmId}/houses/${houseId}`),
  },
  flocks: {
    list: (farmId, houseId) => get(`/farms/${farmId}/houses/${houseId}/flocks`),
    create: (farmId, houseId, data) => post(`/farms/${farmId}/houses/${houseId}/flocks`, data),
    update: (farmId, houseId, flockId, data) =>
      patch(`/farms/${farmId}/houses/${houseId}/flocks/${flockId}`, data),
  },
  flockChecks: {
    list: (farmId, houseId) => get(`/farms/${farmId}/houses/${houseId}/flock-checks`),
    submit: (farmId, houseId, data) => post(`/farms/${farmId}/houses/${houseId}/flock-checks`, data),
    get: (farmId, houseId, checkId) => get(`/farms/${farmId}/houses/${houseId}/flock-checks/${checkId}`),
    comparison: (farmId, houseId, checkId) =>
      get(`/farms/${farmId}/houses/${houseId}/flock-checks/${checkId}/comparison`),
  },
  inspections: {
    list: (farmId, houseId) => get(`/farms/${farmId}/houses/${houseId}/inspections`),
    create: (farmId, houseId, data) => post(`/farms/${farmId}/houses/${houseId}/inspections`, data),
  },
  alerts: {
    // `resolved` is the meaningful "is this actually handled" filter; `acknowledged`
    // ("has a farmer seen it") is kept for backward compatibility. Pass either/both,
    // e.g. api.alerts.list({ resolved: false }).
    list: ({ acknowledged, resolved } = {}) => {
      const params = new URLSearchParams()
      if (acknowledged !== undefined) params.set('acknowledged', acknowledged)
      if (resolved !== undefined) params.set('resolved', resolved)
      const qs = params.toString()
      return get(`/alerts${qs ? `?${qs}` : ''}`)
    },
    acknowledge: (alertId) => post(`/alerts/${alertId}/acknowledge`),
    resolve: (alertId) => post(`/alerts/${alertId}/resolve`),
  },
  analytics: {
    houseTrends: (farmId, houseId, limit) =>
      get(`/farms/${farmId}/houses/${houseId}/analytics/trends${limit ? `?limit=${limit}` : ''}`),
    compareHouses: (farmId) => get(`/farms/${farmId}/analytics/compare-houses`),
    trendInsights: (farmId) => get(`/farms/${farmId}/analytics/trend-insights`),
    dailyBrief: (farmId) => get(`/farms/${farmId}/daily-brief`),
  },
  ask: (question, { houseId, farmId } = {}) => post('/ask', { question, house_id: houseId, farm_id: farmId }),
  askExplain: (farmId, houseId, checkId) =>
    post('/ask/explain', { farm_id: farmId, house_id: houseId, check_id: checkId }),
  askDailyBrief: (farmId) => get(`/ask/daily-brief${farmId ? `?farm_id=${farmId}` : ''}`),
  media: {
    upload: (file, resourceType = 'image') => {
      const form = new FormData()
      form.append('file', file)
      return apiFetch(`/media/upload?resource_type=${resourceType}`, { method: 'POST', body: form })
    },
  },
}
