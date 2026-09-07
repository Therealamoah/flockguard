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
  },
  inspections: {
    list: (farmId, houseId) => get(`/farms/${farmId}/houses/${houseId}/inspections`),
    create: (farmId, houseId, data) => post(`/farms/${farmId}/houses/${houseId}/inspections`, data),
  },
  alerts: {
    list: (acknowledged) =>
      get(`/alerts${acknowledged !== undefined ? `?acknowledged=${acknowledged}` : ''}`),
    acknowledge: (alertId) => post(`/alerts/${alertId}/acknowledge`),
  },
  analytics: {
    houseTrends: (farmId, houseId, limit) =>
      get(`/farms/${farmId}/houses/${houseId}/analytics/trends${limit ? `?limit=${limit}` : ''}`),
    compareHouses: (farmId) => get(`/farms/${farmId}/analytics/compare-houses`),
  },
  ask: (question) => post('/ask', { question }),
  media: {
    upload: (file, resourceType = 'image') => {
      const form = new FormData()
      form.append('file', file)
      return apiFetch(`/media/upload?resource_type=${resourceType}`, { method: 'POST', body: form })
    },
  },
}
