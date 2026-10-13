import { geocode } from '../api'
import type { Place } from '../types'

const COORDS = /^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/

/** A place from text like "39.74, -104.99", or null. */
export function parseCoords(text: string): Place | null {
  const match = COORDS.exec(text)
  if (!match) return null
  const [lat, lon] = [Number(match[1]), Number(match[2])]
  return Math.abs(lat) <= 90 && Math.abs(lon) <= 180 ? { label: `${lat}, ${lon}`, lat, lon } : null
}

/** Coordinates as typed, otherwise the top geocoding match. */
export async function resolvePlace(text: string): Promise<Place> {
  const coords = parseCoords(text)
  if (coords) return coords
  const [best] = await geocode(text.trim())
  if (!best) throw new Error(`No place found for "${text.trim()}".`)
  return best
}
