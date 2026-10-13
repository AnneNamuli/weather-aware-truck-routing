import type { Heatmap, Place, Plan, PlanRequest } from './types'

// Same origin unless the build points it elsewhere (GitHub Pages).
const BASE = import.meta.env.VITE_API_BASE ?? '/api'

// DRF errors come as {detail} or {field: [messages]}.
function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === 'object') {
    const entries = Object.entries(body as Record<string, unknown>)
    if ('detail' in body) return String((body as { detail: unknown }).detail)
    const parts = entries.map(([field, value]) => {
      const message = Array.isArray(value)
        ? value.join(' ')
        : typeof value === 'object'
          ? errorMessage(value, status)
          : String(value)
      return field === 'non_field_errors' ? message : `${field.replace(/_/g, ' ')}: ${message}`
    })
    if (parts.length) return parts.join(' · ')
  }
  return `Request failed (HTTP ${status})`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
  } catch {
    throw new Error('Cannot reach the server. Is the backend running?')
  }
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new Error(errorMessage(body, response.status))
  return body as T
}

/** Ping the API so a sleeping host starts waking before the first search. */
export function wakeServer() {
  fetch(`${BASE}/health`).catch(() => {})
}

/** Place suggestions for `query`. */
export async function geocode(query: string, signal?: AbortSignal): Promise<Place[]> {
  const data = await request<{ results: Place[] }>(`/geocode?q=${encodeURIComponent(query)}`, { signal })
  return data.results
}

/** Plan a trip: three routes with checkpoint weather and a recommendation. */
export function planTrip(tripRequest: PlanRequest, signal?: AbortSignal): Promise<Plan> {
  return request<Plan>('/plan', { method: 'POST', body: JSON.stringify(tripRequest), signal })
}

/** 0-48 h weather grid along the plan's routes. */
export function fetchHeatmap(plan: Plan, signal?: AbortSignal): Promise<Heatmap> {
  return request<Heatmap>('/heatmap', {
    method: 'POST',
    body: JSON.stringify({
      corridor: plan.routes.map((route) => route.corridor),
      departure: plan.departure,
      load_lbs: plan.load_lbs,
    }),
    signal,
  })
}
