import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchHeatmap, planTrip, wakeServer } from './api'
import ForecastPanel from './components/ForecastPanel'
import MapKey from './components/map/MapKey'
import MapView from './components/map/MapView'
import PlanForm from './components/PlanForm'
import RoutePanel from './components/RoutePanel'
import TripSummary from './components/TripSummary'
import { frameAt, sliderTime } from './lib/forecast'
import type { HeatLayer, Heatmap, Plan, PlanRequest } from './types'
import './App.css'

const PLAY_MS_PER_HOUR = 350
const SLOW_REQUEST_MS = 5000

/** Planner page: form and results on the left, map on the right. */
export default function App() {
  const [plan, setPlan] = useState<Plan | null>(null)
  const [planning, setPlanning] = useState(false)
  const [slow, setSlow] = useState(false)
  const [trip, setTrip] = useState<PlanRequest | null>(null)
  const [editing, setEditing] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [focused, setFocused] = useState<{ routeId: string; index: number } | null>(null)

  const [heatmap, setHeatmap] = useState<Heatmap | null>(null)
  const [heatLoading, setHeatLoading] = useState(false)
  const [heatError, setHeatError] = useState<string | null>(null)
  const [showHeat, setShowHeat] = useState(true)
  const [layer, setLayer] = useState<HeatLayer>('risk')
  const [hour, setHour] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [hoverValue, setHoverValue] = useState<number | null>(null)

  // Free hosts sleep when idle: wake the API early and explain a slow first request.
  useEffect(() => wakeServer(), [])
  useEffect(() => {
    if (!planning) return
    const id = window.setTimeout(() => setSlow(true), SLOW_REQUEST_MS)
    return () => {
      window.clearTimeout(id)
      setSlow(false)
    }
  }, [planning])

  // Aborted when a newer request starts, so a slow old response can't win.
  const planRequest = useRef<AbortController | null>(null)
  const heatmapRequest = useRef<AbortController | null>(null)

  const loadHeatmap = useCallback((forPlan: Plan) => {
    heatmapRequest.current?.abort()
    const request = new AbortController()
    heatmapRequest.current = request
    setHeatmap(null)
    setHeatError(null)
    setHeatLoading(true)
    fetchHeatmap(forPlan, request.signal)
      .then(setHeatmap)
      .catch((failure: Error) => {
        if (!request.signal.aborted) setHeatError(failure.message)
      })
      .finally(() => {
        if (!request.signal.aborted) setHeatLoading(false)
      })
  }, [])

  const submit = useCallback(
    (tripRequest: PlanRequest) => {
      planRequest.current?.abort()
      heatmapRequest.current?.abort()
      const request = new AbortController()
      planRequest.current = request
      setPlanning(true)
      setError(null)
      setPlaying(false)
      // Clear the old trip so a failed search doesn't leave it on screen.
      setPlan(null)
      setTrip(null)
      setSelectedId(null)
      setFocused(null)
      setHeatmap(null)
      setHeatError(null)
      setHeatLoading(false)
      planTrip(tripRequest, request.signal)
        .then((newPlan) => {
          setPlan(newPlan)
          setTrip(tripRequest)
          setEditing(false)
          setSelectedId(newPlan.recommended_route_id)
          setFocused(null)
          setHour(0)
          loadHeatmap(newPlan)
        })
        .catch((failure: Error) => {
          if (!request.signal.aborted) setError(failure.message)
        })
        .finally(() => {
          if (!request.signal.aborted) setPlanning(false)
        })
    },
    [loadHeatmap],
  )

  useEffect(() => {
    if (!playing || !heatmap) return
    const timer = window.setInterval(
      () => setHour((currentHour) => (currentHour + 1) % (heatmap.hours + 1)),
      PLAY_MS_PER_HOUR,
    )
    return () => window.clearInterval(timer)
  }, [playing, heatmap])

  const selectRoute = useCallback((id: string) => {
    setSelectedId(id)
    setFocused(null)
  }, [])

  const focusCheckpoint = useCallback((routeId: string, index: number) => setFocused({ routeId, index }), [])

  return (
    <div className="app">
      <aside className="sidebar">
        <header className="brand">
          <div className="logo" aria-hidden>
            ⛟
          </div>
          <h1>Weather-Aware Truck Routing</h1>
        </header>

        {trip && !editing && <TripSummary trip={trip} onEdit={() => setEditing(true)} />}
        {/* Hidden, not unmounted, so the inputs keep their values. */}
        <div hidden={Boolean(trip) && !editing}>
          <PlanForm loading={planning} onSubmit={submit} />
        </div>

        {planning && slow && (
          <p className="hint" role="status">
            Waking the API server. The first request after a quiet period can take up to a minute.
          </p>
        )}

        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}

        {plan && selectedId && (
          <RoutePanel
            plan={plan}
            selectedId={selectedId}
            onSelect={selectRoute}
            onFocusCheckpoint={focusCheckpoint}
            focused={focused}
          />
        )}

        {!plan && !planning && <p className="empty">Compares 3 routes by forecast weather at the truck's ETA.</p>}
      </aside>

      <main className="map-wrap">
        <MapView
          plan={plan}
          endpoints={trip && { start: trip.origin.label, end: trip.destination.label }}
          selectedId={selectedId}
          onSelect={selectRoute}
          focused={focused}
          heatmap={heatmap}
          showHeat={showHeat}
          layer={layer}
          hour={hour}
          frame={heatmap && plan ? frameAt(heatmap, plan.departure, hour) : 0}
          onHover={setHoverValue}
        />
        {plan && (
          <ForecastPanel
            heatmap={heatmap}
            loading={heatLoading}
            error={heatError}
            onRetry={() => loadHeatmap(plan)}
            layer={layer}
            onLayer={setLayer}
            hour={hour}
            time={sliderTime(plan.departure, hour)}
            onHour={setHour}
            playing={playing}
            onPlaying={setPlaying}
            visible={showHeat}
            onVisible={setShowHeat}
            hoverValue={showHeat ? hoverValue : null}
          />
        )}
        {plan && <MapKey />}
        {planning && (
          <div className="map-busy" role="status">
            <div className="map-busy-card">
              <span className="spinner" aria-hidden /> Finding routes and checking the weather along each one…
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
