import { formatDateTime } from '../lib/format'
import type { PlanRequest } from '../types'

// Replaces the form after planning so the results start at the top.
export default function TripSummary({ trip, onEdit }: { trip: PlanRequest; onEdit: () => void }) {
  return (
    <section className="trip-summary" aria-label="Planned trip">
      <div>
        <strong>
          {trip.origin.label} → {trip.destination.label}
        </strong>
        <span className="muted">
          {formatDateTime(trip.departure)} · {trip.load_lbs.toLocaleString()} lb · checkpoint every{' '}
          {trip.interval_miles} mi
        </span>
      </div>
      <button type="button" className="secondary" onClick={onEdit}>
        Edit trip
      </button>
    </section>
  )
}
