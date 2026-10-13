/** Seconds as '4h 05m'. */
export function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const minutesPastHour = minutes % 60
  return hours ? `${hours}h ${String(minutesPastHour).padStart(2, '0')}m` : `${minutesPastHour}m`
}

const shortTimeFormat = new Intl.DateTimeFormat(undefined, { weekday: 'short', hour: 'numeric', minute: '2-digit' })
const fullDateTimeFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'short',
  month: 'short',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
  timeZoneName: 'short',
})

/** Weekday and time, e.g. 'Tue 14:05'. */
export const formatTime = (iso: string | Date) => shortTimeFormat.format(new Date(iso))
/** Date, time and time zone. */
export const formatDateTime = (iso: string | Date) => fullDateTimeFormat.format(new Date(iso))

// Keep the forecast's precision: rounding 0.496 in/hr snow (Low) to "0.5" would read as Moderate.
/** One decimal, the forecast's precision. */
export const formatMph = (mph: number) => mph.toFixed(1)
/** Up to three decimals, trailing zeros dropped. */
export const formatInchesPerHour = (inches: number) => String(Number(inches.toFixed(3)))

/** Whole miles, or one decimal under 10. */
export const formatMiles = (miles: number) =>
  `${miles.toLocaleString(undefined, { maximumFractionDigits: miles < 10 ? 1 : 0 })} mi`

/** 'YYYY-MM-DDTHH:mm' in local time, as <input type="datetime-local"> expects. */
export function toLocalInput(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}
