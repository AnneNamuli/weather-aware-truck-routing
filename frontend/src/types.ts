export type RiskLevel = 0 | 1 | 2 | 3 | 4

export interface Place {
  label: string
  lat: number
  lon: number
}

export interface Checkpoint {
  index: number
  mile: number
  covers_miles: number
  lat: number
  lon: number
  eta: string
  elapsed_s: number
  wind_mph: number
  gust_mph: number
  rain_in_hr: number
  snow_in_hr: number
  risk: RiskLevel
  risk_label: string
  levels: { wind: RiskLevel; rain: RiskLevel; snow: RiskLevel }
  driver: string
  load_note: string | null
}

export interface Route {
  id: string
  roads: string
  distance_miles: number
  duration_s: number
  departure: string
  arrival: string
  /** [lat, lon, elapsed seconds since departure] */
  geometry: [number, number, number][]
  checkpoints: Checkpoint[]
  risk_miles: Record<'Low' | 'Moderate' | 'High' | 'Severe' | 'No Travel', number>
  avg_risk: number
  has_no_travel: boolean
  why_not_recommended: string | null
  corridor: [number, number][]
  rank: number
}

export interface Plan {
  departure: string
  load_lbs: number
  interval_miles: number
  recommended_route_id: string
  recommendation_reasons: string[]
  warnings: string[]
  routes: Route[]
}

export type HeatLayer = 'risk' | 'wind' | 'gust' | 'rain' | 'snow'

export interface Heatmap {
  hours: number
  times: string[]
  bounds: [[number, number], [number, number]]
  nx: number
  ny: number
  /** Row-major, row 0 = north */
  cells: number[]
  /** layers[layer][hour][i] belongs to cells[i] */
  layers: Record<HeatLayer, number[][]>
}

export interface PlanRequest {
  origin: Place
  destination: Place
  departure: string
  load_lbs: number
  interval_miles: 10 | 25 | 50
}
