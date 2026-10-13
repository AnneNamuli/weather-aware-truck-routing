import { useState } from 'react'
import { toLocalInput } from '../lib/format'
import { resolvePlace } from '../lib/place'
import type { Place, PlanRequest } from '../types'
import PlaceInput from './PlaceInput'

const SAMPLES: { name: string; origin: Place; destination: Place }[] = [
  {
    name: 'Dallas → Houston',
    origin: { label: 'Dallas, Texas, US', lat: 32.7763, lon: -96.7969 },
    destination: { label: 'Houston, Texas, US', lat: 29.7589, lon: -95.3677 },
  },
  {
    name: 'Denver → Salt Lake City',
    origin: { label: 'Denver, Colorado, US', lat: 39.7392, lon: -104.9903 },
    destination: { label: 'Salt Lake City, Utah, US', lat: 40.7608, lon: -111.891 },
  },
  {
    name: 'Chicago → Minneapolis',
    origin: { label: 'Chicago, Illinois, US', lat: 41.8781, lon: -87.6298 },
    destination: { label: 'Minneapolis, Minnesota, US', lat: 44.9778, lon: -93.265 },
  },
]

const INTERVALS = [10, 25, 50] as const
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
            onClick={() => {
              setOrigin(sample.origin)
              setDestination(sample.destination)
            }}
          >
            {sample.name}
          </button>
        ))}
      </div>
    </form>
  )
}
