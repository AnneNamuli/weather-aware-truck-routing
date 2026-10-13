import L from 'leaflet'
import { memo, useMemo, useRef } from 'react'
import { CircleMarker, Pane, Polyline, Popup, Tooltip } from 'react-leaflet'
import { formatDuration, formatMiles, formatTime } from '../../lib/format'
import { labelAnchors, riskSegments } from '../../lib/path'
import { RISK_LABELS, riskColor } from '../../lib/risk'
import type { Plan, RiskLevel } from '../../types'
import CheckpointPopup from './CheckpointPopup'
import RouteSummary from './RouteSummary'

// Green is reserved for the recommended route; Low on the others is grey.
const ALTERNATIVE_GREY = '#7c8594'

/** Risk colour, except Low on non-recommended routes, which is grey. */
function displayColor(risk: RiskLevel, isRecommended: boolean): string {
  return risk === 0 && !isRecommended ? ALTERNATIVE_GREY : riskColor(risk)
}

interface RouteLineProps {
  line: [number, number][]
  segments: ReturnType<typeof riskSegments>
  pane: string
  isRecommended: boolean
  outlineWeight: number
}

/** One route: optional dark outline, grey base for alternatives, risk-coloured stretches. */
function RouteLine({ line, segments, pane, isRecommended, outlineWeight }: RouteLineProps) {
  const outlined = outlineWeight > 0
  const coloredSegments = isRecommended ? segments : segments.filter((segment) => segment.risk > 0)
  return (
    <>
      {outlined && (
        <Polyline positions={line} pathOptions={{ pane, color: '#111827', weight: outlineWeight, opacity: 0.85 }} />
      )}
      {!isRecommended && (
        <Polyline
          positions={line}
          pathOptions={{ pane, color: ALTERNATIVE_GREY, weight: outlined ? 5.5 : 5, opacity: outlined ? 1 : 0.6 }}
        />
      )}
      {coloredSegments.map((segment, index) => (
        <Polyline
          key={index}
          positions={segment.points}
          pathOptions={{ pane, color: riskColor(segment.risk), weight: outlined ? 5.5 : 4, opacity: 1 }}
        />
      ))}
    </>
  )
}

interface RouteLayersProps {
  plan: Plan | null
  selectedId: string | null
  onSelect: (id: string) => void
  markers: React.RefObject<Map<string, L.CircleMarker>>
}

// Memoized so moving the slider doesn't re-render hundreds of route and checkpoint layers.
const RouteLayers = memo(function RouteLayers({ plan, selectedId, onSelect, markers }: RouteLayersProps) {
  const lines = useMemo(
    () =>
      new Map(
        plan?.routes.map((route) => [route.id, route.geometry.map(([lat, lon]) => [lat, lon] as [number, number])]) ??
          [],
      ),
    [plan],
  )
  const labelPoints = useMemo(() => labelAnchors(plan?.routes ?? []), [plan])
  const segmentsByRoute = useMemo(
    () => new Map(plan?.routes.map((route) => [route.id, riskSegments(route)]) ?? []),
    [plan],
  )
  const recommendedId = plan?.recommended_route_id
  const recommended = plan?.routes.find((route) => route.id === recommendedId)
  const selectedAlternative = plan?.routes.find((route) => route.id === selectedId && route.id !== recommendedId)
  const backgroundRoutes = plan?.routes.filter((route) => route.id !== recommendedId && route.id !== selectedId) ?? []
  const hitAreas = useRef(new Map<string, L.Polyline>())
  const showRoute = (routeId: string, at?: L.LatLngExpression) => {
    onSelect(routeId)
    hitAreas.current.get(routeId)?.openPopup(at)
  }

  return (
    <>
      {/* Separate panes keep the draw order: alternatives, then recommended, then selected. */}
      <Pane name="routes-background" style={{ zIndex: 410 }}>
        {backgroundRoutes.map((route) => (
          <RouteLine
            key={route.id}
            line={lines.get(route.id)!}
            segments={segmentsByRoute.get(route.id)!}
            pane="routes-background"
            isRecommended={false}
            outlineWeight={0}
          />
        ))}
      </Pane>

      <Pane name="route-recommended" style={{ zIndex: 415 }}>
        {recommended && (
          <RouteLine
            line={lines.get(recommended.id)!}
            segments={segmentsByRoute.get(recommended.id)!}
            pane="route-recommended"
            isRecommended
            outlineWeight={recommended.id === selectedId ? 12 : 9}
          />
        )}
      </Pane>

      <Pane name="route-selected" style={{ zIndex: 420 }}>
        {selectedAlternative && (
          <RouteLine
            line={lines.get(selectedAlternative.id)!}
            segments={segmentsByRoute.get(selectedAlternative.id)!}
            pane="route-selected"
            isRecommended={false}
            outlineWeight={9}
          />
        )}
      </Pane>

      {/* Wide invisible lines so routes are easy to click. */}
      <Pane name="route-hit-areas" style={{ zIndex: 425 }}>
        {plan?.routes.map((route) => (
          <Polyline
            key={route.id}
            ref={(line) => {
              if (line) hitAreas.current.set(route.id, line)
              else hitAreas.current.delete(route.id)
            }}
            positions={lines.get(route.id)!}
            pathOptions={{ pane: 'route-hit-areas', color: '#000', weight: 20, opacity: 0 }}
            eventHandlers={{ click: () => onSelect(route.id) }}
          >
            <Popup pane="popupPane" maxWidth={320}>
              <RouteSummary plan={plan} route={route} />
            </Popup>
          </Polyline>
        ))}
      </Pane>

      <Pane name="checkpoints" style={{ zIndex: 430 }}>
        {plan?.routes.map((route) => {
          const isSelected = route.id === selectedId
          return route.checkpoints.map((checkpoint) => (
            <CircleMarker
              key={`${route.id}:${checkpoint.index}:${isSelected}`}
              ref={(marker) => {
                const markerKey = `${route.id}:${checkpoint.index}`
                if (marker) markers.current.set(markerKey, marker)
                else markers.current.delete(markerKey)
              }}
              center={[checkpoint.lat, checkpoint.lon]}
              radius={isSelected ? 5.5 : 2.5}
              pathOptions={{
                pane: 'checkpoints',
                color: isSelected ? '#fff' : displayColor(checkpoint.risk, route.id === recommendedId),
                weight: isSelected ? 1.5 : 0,
                fillColor: displayColor(checkpoint.risk, route.id === recommendedId),
                fillOpacity: isSelected ? 1 : 0.9,
              }}
              eventHandlers={
                isSelected ? undefined : { click: () => showRoute(route.id, [checkpoint.lat, checkpoint.lon]) }
              }
            >
              <Tooltip pane="tooltipPane" direction="top" offset={[0, -4]}>
                {route.id} · mi {Math.round(checkpoint.mile)} · ETA {formatTime(checkpoint.eta)} ·{' '}
                {RISK_LABELS[checkpoint.risk]}
              </Tooltip>
              {isSelected && (
                <Popup pane="popupPane">
                  <CheckpointPopup route={route} checkpoint={checkpoint} />
                </Popup>
              )}
            </CircleMarker>
          ))
        })}

        {plan?.routes.map((route) => {
          const labelPoint = labelPoints.get(route.id)!
          const rec = route.id === plan.recommended_route_id
          const severeMiles = route.risk_miles.Severe + route.risk_miles['No Travel']
          const highMiles = route.risk_miles.High
          return (
            <CircleMarker
              key={`label-${route.id}`}
              center={[labelPoint[0], labelPoint[1]]}
              radius={0}
              pathOptions={{ pane: 'checkpoints', opacity: 0, fillOpacity: 0 }}
            >
              <Tooltip
                pane="tooltipPane"
                permanent
                interactive
                direction="center"
                className={`route-label${route.id === selectedId ? ' selected' : ''}${rec ? ' rec' : ''}`}
                eventHandlers={{ click: () => showRoute(route.id, [labelPoint[0], labelPoint[1]]) }}
              >
                <b>
                  {rec ? '★ ' : ''}
                  {route.id}
                </b>{' '}
                {formatDuration(route.duration_s)} · {formatMiles(route.distance_miles)}
                {severeMiles > 0 && <span className="rl-severe"> · {severeMiles} Severe mi</span>}
                {highMiles > 0 && <span className="rl-high"> · {highMiles} High mi</span>}
              </Tooltip>
            </CircleMarker>
          )
        })}
      </Pane>
    </>
  )
})

export default RouteLayers
