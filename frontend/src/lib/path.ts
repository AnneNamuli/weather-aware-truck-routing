import type { Checkpoint, Route } from '../types'

type LatLng = [number, number]

/** Truck position `elapsedSeconds` after departure, clamped to the route's ends. */
export function positionAt(route: Route, elapsedSeconds: number): LatLng {
  const vertices = route.geometry // [lat, lon, elapsed seconds]
  const first = vertices[0]
  const last = vertices[vertices.length - 1]
  if (elapsedSeconds <= 0) return [first[0], first[1]]
  if (elapsedSeconds >= last[2]) return [last[0], last[1]]

  let before = 0
  let after = vertices.length - 1
  while (after - before > 1) {
    const middle = (before + after) >> 1
    if (vertices[middle][2] <= elapsedSeconds) before = middle
    else after = middle
  }
  const [fromLat, fromLon, fromTime] = vertices[before]
  const [toLat, toLon, toTime] = vertices[after]
  const fraction = toTime > fromTime ? (elapsedSeconds - fromTime) / (toTime - fromTime) : 0
  return [fromLat + (toLat - fromLat) * fraction, fromLon + (toLon - fromLon) * fraction]
}

interface RiskSegment {
  risk: Checkpoint['risk']
  points: LatLng[]
}

/** Stretches of the route coloured by the checkpoint covering them (same split as the backend). */
export function riskSegments(route: Route): RiskSegment[] {
  const checkpoints = route.checkpoints
  // Geometry carries time, not distance, so the handovers are in seconds.
  const handoverTimes = checkpoints
    .slice(0, -1)
    .map((checkpoint, index) => (checkpoint.elapsed_s + checkpoints[index + 1].elapsed_s) / 2)

  const segments: RiskSegment[] = []
  let coveringCheckpoint = 0
  let current: RiskSegment = { risk: checkpoints[0].risk, points: [] }
  for (const [lat, lon, elapsedSeconds] of route.geometry) {
    while (coveringCheckpoint < handoverTimes.length && elapsedSeconds > handoverTimes[coveringCheckpoint]) {
      const handoverPoint = positionAt(route, handoverTimes[coveringCheckpoint])
      current.points.push(handoverPoint)
      coveringCheckpoint++
      const nextRisk = checkpoints[coveringCheckpoint].risk
      if (nextRisk !== current.risk) {
        segments.push(current)
        current = { risk: nextRisk, points: [handoverPoint] }
      }
    }
    current.points.push([lat, lon])
  }
  segments.push(current)
  return segments.filter((segment) => segment.points.length > 1)
}

const LABEL_CANDIDATES = 24
// Labels stay away from the ends, where the start/end pins are.
const LABEL_RANGE_START = 0.15
const LABEL_RANGE_END = 0.85
const MAX_VERTICES_COMPARED = 150 // per route

// Only used for comparisons, so no need for real units.
function squaredDistance([lat1, lon1]: LatLng, [lat2, lon2]: LatLng): number {
  const lonScale = Math.cos((((lat1 + lat2) / 2) * Math.PI) / 180)
  return (lat1 - lat2) ** 2 + ((lon1 - lon2) * lonScale) ** 2
}

/** Smallest `squaredDistance` from `point` to any of `others`. */
function nearestSquaredDistance(point: LatLng, others: LatLng[]): number {
  return others.reduce((nearest, other) => Math.min(nearest, squaredDistance(point, other)), Infinity)
}

/** Label position per route: the spot farthest from the other routes and labels, so they don't stack. */
export function labelAnchors(routes: Route[]): Map<string, LatLng> {
  const anchors = new Map<string, LatLng>()
  for (const route of routes) {
    const otherRouteVertices = routes
      .filter((other) => other.id !== route.id)
      .flatMap((other) => {
        const stride = Math.max(1, Math.ceil(other.geometry.length / MAX_VERTICES_COMPARED))
        return other.geometry.filter((_, index) => index % stride === 0).map(([lat, lon]): LatLng => [lat, lon])
      })
    const placedLabels = [...anchors.values()]

    let bestAnchor: LatLng | null = null
    let bestScore = -1
    for (let candidate = 0; candidate <= LABEL_CANDIDATES; candidate++) {
      const fraction = LABEL_RANGE_START + ((LABEL_RANGE_END - LABEL_RANGE_START) * candidate) / LABEL_CANDIDATES
      const [lat, lon] = route.geometry[Math.floor((route.geometry.length - 1) * fraction)]
      const point: LatLng = [lat, lon]
      const clearance = Math.min(
        nearestSquaredDistance(point, otherRouteVertices),
        nearestSquaredDistance(point, placedLabels),
      )
      // With nothing else around (a single route), prefer the middle.
      const middleBias = clearance === Infinity ? -Math.abs(fraction - 0.5) : 0
      const score = clearance === Infinity ? middleBias : clearance
      if (bestAnchor === null || score > bestScore) {
        bestAnchor = point
        bestScore = score
      }
    }
    anchors.set(route.id, bestAnchor!)
  }
  return anchors
}
