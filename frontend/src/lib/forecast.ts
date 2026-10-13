import type { Heatmap } from '../types'

const MS_PER_HOUR = 3_600_000

/** Frame nearest departure + hour. Frames start on the hour, so 07:30 at +0h uses 08:00. */
export function frameAt(heatmap: Heatmap, departure: string, hour: number): number {
  const offset = (Date.parse(departure) - Date.parse(heatmap.times[0])) / MS_PER_HOUR
  return Math.min(heatmap.times.length - 1, Math.round(hour + offset))
}

/** The time the slider shows: departure + `hour`. */
export const sliderTime = (departure: string, hour: number) => new Date(Date.parse(departure) + hour * MS_PER_HOUR)
