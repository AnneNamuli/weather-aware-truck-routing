import L from 'leaflet'
import { useEffect, useMemo, useRef } from 'react'
import { MapContainer, Marker, Pane, TileLayer, useMap } from 'react-leaflet'
import { positionAt } from '../../lib/path'
import type { HeatLayer, Heatmap, Plan } from '../../types'
import HeatmapOverlay from './HeatmapOverlay'
import { endpointIcon, truckIcon } from './icons'
import RouteLayers from './RouteLayers'

interface Props {
  endpoints: { start: string; end: string } | null
  plan: Plan | null
  selectedId: string | null
  onSelect: (id: string) => void
  focused: { routeId: string; index: number } | null
  heatmap: Heatmap | null
  showHeat: boolean
  layer: HeatLayer
  /** Hours after departure; places the trucks. */
  hour: number
  frame: number
  onHover: (value: number | null) => void
}

const US_CENTER: [number, number] = [39.5, -98.35]
const SECONDS_PER_HOUR = 3600
// Space kept clear of routes when zooming to a trip.
const MAP_KEY_WIDTH_PX = 300
const FORECAST_PANEL_HEIGHT_PX = 190
const START_LABEL_HEIGHT_PX = 70
const MAP_EDGE_PX = 40
const SHOWS_MAP_KEY_MIN_WIDTH_PX = 900
const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas'
const ATTRIBUTION =
  'Basemap &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors · Routing: OSRM · Weather: <a href="https://open-meteo.com">Open-Meteo</a>'

/** Zoom to the plan's routes when a new plan arrives. */
function FitToPlan({ plan }: { plan: Plan | null }) {
  const map = useMap()
  useEffect(() => {
    if (!plan) return
    const bounds = L.latLngBounds(
      plan.routes.flatMap((route) => route.geometry.map(([lat, lon]) => [lat, lon] as [number, number])),
    )
    const rightPadding = map.getSize().x > SHOWS_MAP_KEY_MIN_WIDTH_PX ? MAP_KEY_WIDTH_PX : MAP_EDGE_PX
    map.fitBounds(bounds, {
      paddingTopLeft: [MAP_EDGE_PX, START_LABEL_HEIGHT_PX],
      paddingBottomRight: [rightPadding, FORECAST_PANEL_HEIGHT_PX],
    })
  }, [plan, map])
  return null
}

/** Fly to a checkpoint picked in the sidebar and open its popup. */
function FocusCheckpoint({
  focused,
  markers,
}: {
  focused: Props['focused']
  markers: React.RefObject<Map<string, L.CircleMarker>>
}) {
  const map = useMap()
  useEffect(() => {
    if (!focused) return
    const marker = markers.current.get(`${focused.routeId}:${focused.index}`)
    if (!marker) return
    map.flyTo(marker.getLatLng(), Math.max(map.getZoom(), 9), { duration: 0.6 })
    marker.openPopup()
  }, [focused, map, markers])
  return null
}

/** The map: basemap, heatmap, routes, trucks and start/end pins. */
export default function MapView({
  plan,
  endpoints,
  selectedId,
  onSelect,
  focused,
  heatmap,
  showHeat,
  layer,
  hour,
  frame,
  onHover,
}: Props) {
  const markers = useRef(new Map<string, L.CircleMarker>())

  const first = plan?.routes[0].geometry[0]
  const last = plan?.routes[0].geometry.at(-1)
  const startPin = useMemo(() => endpoints && endpointIcon('start', endpoints.start), [endpoints])
  const endPin = useMemo(() => endpoints && endpointIcon('end', endpoints.end), [endpoints])
  const sliderElapsed = heatmap ? hour * SECONDS_PER_HOUR : null
  const icons = useMemo(
    () =>
      new Map(plan?.routes.map((route) => [route.id, [truckIcon(route.id, false), truckIcon(route.id, true)]]) ?? []),
    [plan],
  )

  return (
    <MapContainer center={US_CENTER} zoom={4} preferCanvas className="map" zoomControl>
      <TileLayer
        url={`${ESRI}/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}`}
        attribution={ATTRIBUTION}
        maxNativeZoom={16}
        maxZoom={18}
      />
      {/* Labels above the heatmap so city names stay readable. */}
      <Pane name="labels" style={{ zIndex: 380, pointerEvents: 'none' }}>
        <TileLayer
          url={`${ESRI}/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}`}
          pane="labels"
          maxNativeZoom={16}
          maxZoom={18}
        />
      </Pane>
      <FitToPlan plan={plan} />
      <FocusCheckpoint focused={focused} markers={markers} />

      <Pane name="heat" style={{ zIndex: 350 }}>
        {heatmap && showHeat && (
          <HeatmapOverlay data={heatmap} layer={layer} hour={frame} pane="heat" onHover={onHover} />
        )}
      </Pane>

      <RouteLayers plan={plan} selectedId={selectedId} onSelect={onSelect} markers={markers} />

      {sliderElapsed !== null &&
        plan?.routes.map((route) => {
          const position = positionAt(route, sliderElapsed)
          const pair = icons.get(route.id)
          return pair ? (
            <Marker
              key={`truck-${route.id}`}
              position={position}
              icon={pair[route.id === selectedId ? 1 : 0]}
              interactive={false}
              zIndexOffset={route.id === selectedId ? 1000 : 0}
            />
          ) : null
        })}

      {/* Above the trucks, which sit on the start pin before departure. */}
      {startPin && endPin && first && last && (
        <>
          <Marker position={[first[0], first[1]]} icon={startPin} interactive={false} zIndexOffset={3000} />
          <Marker position={[last[0], last[1]]} icon={endPin} interactive={false} zIndexOffset={3000} />
        </>
      )}
    </MapContainer>
  )
}
