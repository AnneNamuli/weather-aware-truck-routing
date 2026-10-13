import { formatDuration, formatInchesPerHour, formatMiles, formatMph, formatTime } from '../lib/format'
import { RISK_LABELS, riskColor } from '../lib/risk'
import { useEffect, useRef } from 'react'
import type { Plan, RiskLevel, Route } from '../types'
import RiskBar from './RiskBar'

/** Coloured dot and label for a risk level. */
function RiskChip({ level }: { level: RiskLevel }) {
  return (
    <span className="risk-chip" style={{ '--risk': riskColor(level) } as React.CSSProperties}>
      {RISK_LABELS[level]}
    </span>
  )
}

/** One route's time, distance, arrival and risk miles. */
function RouteCard({
  route,
  recommended,
  selected,
  onSelect,
}: {
  route: Route
  recommended: boolean
  selected: boolean
  onSelect: () => void
}) {
  const riskMiles = route.risk_miles
  const card = useRef<HTMLButtonElement>(null)
  // Selection can come from the map, so bring the card into view.
  useEffect(() => {
    if (selected) card.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [selected])
  return (
    <button
      ref={card}
      className={`route-card${selected ? ' selected' : ''}${recommended ? ' recommended' : ''}`}
      onClick={onSelect}
      aria-pressed={selected}
    >
      <div className="route-card-head">
        <span className="route-badge">{route.id}</span>
        <div className="route-title">
          <strong>Route {route.id}</strong>
          <span className="roads" title={route.roads}>
            {route.roads ? `via ${route.roads}` : 'Alternate route'}
          </span>
        </div>
        {route.has_no_travel && <span className="nt-tag">No Travel</span>}
        {recommended ? <span className="rec-tag">★ Recommended</span> : <span className="rank-tag">#{route.rank}</span>}
      </div>

      <div className="route-stats">
        <div>
          <span className="stat">{formatDuration(route.duration_s)}</span>
          <span className="stat-label">drive time</span>
        </div>
        <div>
          <span className="stat">{formatMiles(route.distance_miles)}</span>
          <span className="stat-label">distance</span>
        </div>
        <div>
          <span className="stat">{formatTime(route.arrival)}</span>
          <span className="stat-label">arrival</span>
        </div>
      </div>

      <RiskBar route={route} />
      <div className="risk-miles">
        <span className={riskMiles['No Travel'] > 0 ? 'bad' : ''}>
          No Travel <b>{riskMiles['No Travel']}</b> mi
        </span>
        <span className={riskMiles.Severe > 0 ? 'bad' : ''}>
          Severe <b>{riskMiles.Severe}</b> mi
        </span>
        <span className={riskMiles.High > 0 ? 'warn' : ''}>
          High <b>{riskMiles.High}</b> mi
        </span>
        <span title="Distance-weighted average risk level: 0 = Low … 4 = No Travel">
          avg risk <b>{route.avg_risk.toFixed(2)}</b>
        </span>
      </div>
    </button>
  )
}

interface Props {
  plan: Plan
  selectedId: string
  onSelect: (id: string) => void
  onFocusCheckpoint: (routeId: string, index: number) => void
  focused: { routeId: string; index: number } | null
}

/** Recommendation, route cards and the selected route's checkpoints. */
export default function RoutePanel({ plan, selectedId, onSelect, onFocusCheckpoint, focused }: Props) {
  const best = plan.routes.find((route) => route.id === plan.recommended_route_id)!
  const selected = plan.routes.find((route) => route.id === selectedId) ?? best
  return (
    <section className="results" aria-live="polite">
      {plan.warnings.map((warning) => (
        <div className="warning" key={warning}>
          {warning}
        </div>
      ))}

      <div className="recommendation">
        <div className="rec-head">
          <span className="eyebrow">Recommended</span>
          <strong>
            Route {best.id} · {formatDuration(best.duration_s)}
          </strong>
        </div>
        {plan.recommendation_reasons.length > 0 && (
          <ul>
            {plan.recommendation_reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        )}
        <p className="criteria">Ranked: Severe → High miles → avg risk → time</p>
      </div>

      <p className="hint">Click a route card or a line on the map to see that route's checkpoints.</p>
      <div className="route-list">
        {[...plan.routes]
          .sort((first, second) => first.rank - second.rank)
          .map((route) => (
            <RouteCard
              key={route.id}
              route={route}
              recommended={route.id === best.id}
              selected={route.id === selected.id}
              onSelect={() => onSelect(route.id)}
            />
          ))}
      </div>

      <div className="checkpoints">
        <h3>
          Route {selected.id} checkpoints{' '}
          <span className="muted">
            ({selected.checkpoints.length}, every {plan.interval_miles} mi)
          </span>
        </h3>
        <table>
          <thead>
            <tr>
              <th>Mile</th>
              <th>ETA</th>
              <th title="Sustained wind (gust)">Wind</th>
              <th title="Rain in/hr">Rain</th>
              <th title="Snow in/hr">Snow</th>
              <th>Risk</th>
            </tr>
          </thead>
          <tbody>
            {selected.checkpoints.map((checkpoint) => (
              <tr
                key={checkpoint.index}
                className={focused?.routeId === selected.id && focused.index === checkpoint.index ? 'focused' : ''}
                onClick={() => onFocusCheckpoint(selected.id, checkpoint.index)}
                tabIndex={0}
                onKeyDown={(event) => event.key === 'Enter' && onFocusCheckpoint(selected.id, checkpoint.index)}
              >
                <td>{Math.round(checkpoint.mile)}</td>
                <td>{formatTime(checkpoint.eta)}</td>
                <td className={checkpoint.levels.wind ? 'hot' : ''}>
                  {formatMph(checkpoint.wind_mph)}
                  <span className="muted"> ({Math.round(checkpoint.gust_mph)})</span>
                </td>
                <td className={checkpoint.levels.rain ? 'hot' : ''}>{formatInchesPerHour(checkpoint.rain_in_hr)}</td>
                <td className={checkpoint.levels.snow ? 'hot' : ''}>{formatInchesPerHour(checkpoint.snow_in_hr)}</td>
                <td>
                  <RiskChip level={checkpoint.risk} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
