import { useState } from 'react'
import { toLocalInput } from '../lib/format'
import { resolvePlace } from '../lib/place'
import type { Place, PlanRequest } from '../types'
import PlaceInput from './PlaceInput'

const INTERVALS = [10, 25, 50] as const

// Each sample also sets the load and spacing it is meant to be shown with, and says what it tests.
const SAMPLES: {
  name: string
  tests: string
  origin: Place
  destination: Place
  loadLbs: number
  intervalMiles: (typeof INTERVALS)[number]
}[] = [
  {
    name: 'Dallas → Houston',
    tests: 'Baseline: calm weather, so the fastest route wins. OSRM returns one route; the rest are detours.',
    origin: { label: 'Dallas, Texas, US', lat: 32.7763, lon: -96.7969 },
    destination: { label: 'Houston, Texas, US', lat: 29.7589, lon: -95.3677 },
    loadLbs: 30_000,
    intervalMiles: 25,
  },
  {
    name: 'Cheyenne → Salt Lake City',
    tests: 'Load rule: over 40,000 lb in 35–44 mph wind becomes Severe ("wind + load"), on a windy day.',
    origin: { label: 'Cheyenne, Wyoming, US', lat: 41.14, lon: -104.8202 },
    destination: { label: 'Salt Lake City, Utah, US', lat: 40.7608, lon: -111.891 },
    loadLbs: 45_000,
    intervalMiles: 25,
  },
  {
    name: 'Cape Town → Johannesburg',
    tests: 'Timing: a 15-hour trip, so each checkpoint uses the forecast for when the truck gets there.',
    origin: { label: 'Cape Town, South Africa', lat: -33.9249, lon: 18.4241 },
    destination: { label: 'Johannesburg, South Africa', lat: -26.2041, lon: 28.0473 },
    loadLbs: 30_000,
    intervalMiles: 50,
  },
  {
    name: 'Kampala → Nairobi',
    tests: 'Cross-border trip that goes around Lake Victoria by road.',
    origin: { label: 'Kampala, Uganda', lat: 0.3476, lon: 32.5825 },
    destination: { label: 'Nairobi, Kenya', lat: -1.2921, lon: 36.8219 },
    loadLbs: 30_000,
    intervalMiles: 25,
  },
  {
    name: 'Reykjavík → Akureyri',
    tests: 'Load rule in strong wind: the app avoids a route that "wind + load" makes Severe.',
    origin: { label: 'Reykjavík, Iceland', lat: 64.1466, lon: -21.9426 },
    destination: { label: 'Akureyri, Iceland', lat: 65.6835, lon: -18.0878 },
    loadLbs: 45_000,
    intervalMiles: 25,
  },
  {
    name: 'Reykjavík → Höfn',
    tests: 'High risk: storms on the south coast can reach No Travel; even the best route may get a warning.',
    origin: { label: 'Reykjavík, Iceland', lat: 64.1466, lon: -21.9426 },
    destination: { label: 'Höfn, Iceland', lat: 64.2539, lon: -15.2082 },
    loadLbs: 45_000,
    intervalMiles: 25,
  },
  {
    name: 'Kampala → Antananarivo',
    tests: 'Edge case: Madagascar is an island, so there is no road route.',
    origin: { label: 'Kampala, Uganda', lat: 0.3476, lon: 32.5825 },
    destination: { label: 'Antananarivo, Madagascar', lat: -18.8792, lon: 47.5079 },
    loadLbs: 30_000,
    intervalMiles: 50,
  },
]
const DEFAULT_INTERVAL_MILES = 25
const DEFAULT_LOAD_LBS = '42000'
const MAX_LOAD_LBS = 100_000
const FORECAST_DAYS_AHEAD = 7
const MS_PER_MINUTE = 60_000
const MS_PER_DAY = 86_400_000

interface Props {
  loading: boolean
  onSubmit: (req: PlanRequest) => void
}

/** Trip form: places, departure, load and checkpoint spacing. */
export default function PlanForm({ loading, onSubmit }: Props) {
  const [origin, setOrigin] = useState<Place | null>(null)
  const [destination, setDestination] = useState<Place | null>(null)
  const [originText, setOriginText] = useState('')
  const [destinationText, setDestinationText] = useState('')
  const [resolving, setResolving] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const [departure, setDeparture] = useState(() => {
    const defaultDeparture = new Date(Date.now() + 30 * MS_PER_MINUTE)
    const nextQuarterHour = Math.ceil(defaultDeparture.getMinutes() / 15) * 15
    defaultDeparture.setMinutes(nextQuarterHour, 0, 0)
    return toLocalInput(defaultDeparture)
  })
  const [load, setLoad] = useState(DEFAULT_LOAD_LBS)
  const [spacing, setSpacing] = useState<(typeof INTERVALS)[number]>(DEFAULT_INTERVAL_MILES)
  // What the hovered or focused sample trip tests.
  const [hint, setHint] = useState<string | null>(null)

  // The forecast only reaches about a week ahead.
  const [limits] = useState(() => {
    const now = Date.now()
    return { min: toLocalInput(new Date(now)), max: toLocalInput(new Date(now + FORECAST_DAYS_AHEAD * MS_PER_DAY)) }
  })
  const loadLbs = Number(load)
  // Typed text without a picked suggestion is looked up on submit.
  const filled = (place: Place | null, text: string) => place !== null || text.trim().length > 0
  const valid =
    filled(origin, originText) &&
    filled(destination, destinationText) &&
    departure &&
    load !== '' &&
    loadLbs >= 0 &&
    loadLbs <= MAX_LOAD_LBS

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!valid) return
    setFormError(null)
    setResolving(true)
    let from: Place, to: Place
    try {
      ;[from, to] = await Promise.all([
        origin ?? resolvePlace(originText),
        destination ?? resolvePlace(destinationText),
      ])
    } catch (err) {
      setFormError((err as Error).message)
      return
    } finally {
      setResolving(false)
    }
    setOrigin(from)
    setDestination(to)
    onSubmit({
      origin: from,
      destination: to,
      departure: new Date(departure).toISOString(),
      load_lbs: loadLbs,
      interval_miles: spacing,
    })
  }

  return (
    <form className="plan-form" onSubmit={submit}>
      <PlaceInput
        label="Origin"
        value={origin}
        onChange={setOrigin}
        onTextChange={setOriginText}
        placeholder="City, address, or lat, lon"
      />
      <PlaceInput
        label="Destination"
        value={destination}
        onChange={setDestination}
        onTextChange={setDestinationText}
        placeholder="City, address, or lat, lon"
      />

      <div className="field-row">
        <div className="field">
          <label htmlFor="departure">Departure</label>
          <input
            id="departure"
            type="datetime-local"
            value={departure}
            min={limits.min}
            max={limits.max}
            onChange={(event) => setDeparture(event.target.value)}
            required
          />
        </div>
        <div className="field load-field">
          <label htmlFor="load">Load weight</label>
          <div className="input-suffix">
            <input
              id="load"
              type="number"
              inputMode="numeric"
              min={0}
              max={MAX_LOAD_LBS}
              step={500}
              value={load}
              onChange={(event) => setLoad(event.target.value)}
              aria-describedby="load-help"
              required
            />
            <span>lb</span>
          </div>
        </div>
      </div>
      <p className="field-help" id="load-help">
        Cargo weight. Loads over 30,000 lb hit wind limits sooner.
      </p>

      <div className="field">
        <span className="label" id="interval-label">
          Checkpoint every
        </span>
        <div className="segmented" role="radiogroup" aria-labelledby="interval-label" aria-describedby="interval-help">
          {INTERVALS.map((miles) => (
            <button
              type="button"
              key={miles}
              role="radio"
              aria-checked={spacing === miles}
              className={spacing === miles ? 'on' : ''}
              onClick={() => setSpacing(miles)}
            >
              {miles} mi
            </button>
          ))}
        </div>
        <p className="field-help" id="interval-help">
          Weather is checked at each checkpoint for the time the truck gets there.
        </p>
      </div>

      <button className="primary" type="submit" disabled={!valid || loading || resolving}>
        {resolving || loading ? (
          <>
            <span className="spinner" aria-hidden /> {resolving ? 'Finding places…' : 'Planning…'}
          </>
        ) : (
          'Find safest route'
        )}
      </button>
      {formError && (
        <div className="error" role="alert">
          {formError}
        </div>
      )}

      <div className="samples">
        <span>Try:</span>
        {SAMPLES.map((sample) => (
          <button
            type="button"
            key={sample.name}
            className="link"
            aria-describedby="sample-hint"
            onMouseEnter={() => setHint(sample.tests)}
            onMouseLeave={() => setHint(null)}
            onFocus={() => setHint(sample.tests)}
            onBlur={() => setHint(null)}
            onClick={() => {
              setOrigin(sample.origin)
              setDestination(sample.destination)
              setLoad(String(sample.loadLbs))
              setSpacing(sample.intervalMiles)
            }}
          >
            {sample.name}
          </button>
        ))}
      </div>
      <p className="field-help sample-hint" id="sample-hint" aria-live="polite">
        {hint ?? 'Hover a trip to see what it tests.'}
      </p>
    </form>
  )
}
