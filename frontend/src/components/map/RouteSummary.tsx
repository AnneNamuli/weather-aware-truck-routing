import { formatDateTime, formatDuration, formatMiles } from '../../lib/format'
import { RISK_LABELS, riskColor } from '../../lib/risk'
import type { Plan, RiskLevel, Route } from '../../types'
import RiskBar from '../RiskBar'

/** Popup with everything about one route. */
export default function RouteSummary({ plan, route }: { plan: Plan; route: Route }) {
  const isRecommended = route.id === plan.recommended_route_id
  return (
    <div className="route-summary">
      <div className="route-summary-head">
        <strong>Route {route.id}</strong>
        {isRecommended ? (
          <span className="rec-tag">★ Recommended</span>
        ) : (
          <span className="rank-tag">
            #{route.rank} of {plan.routes.length}
          </span>
        )}
        {route.has_no_travel && <span className="nt-tag">No Travel</span>}
      </div>
      {route.roads && <div className="muted small">via {route.roads}</div>}

      <dl className="route-summary-facts">
        <dt>Drive time</dt>
        <dd>{formatDuration(route.duration_s)}</dd>
        <dt>Distance</dt>
        <dd>{formatMiles(route.distance_miles)}</dd>
        <dt>Departs</dt>
        <dd>{formatDateTime(route.departure)}</dd>
        <dt>Arrives</dt>
        <dd>{formatDateTime(route.arrival)}</dd>
        <dt>Average risk</dt>
        <dd title="Average of the risk levels, weighted by miles">
          {route.avg_risk.toFixed(2)} <span className="muted">(0 Low – 4 No Travel)</span>
        </dd>
      </dl>

      <div className="route-summary-heading">Miles by weather risk</div>
      <RiskBar route={route} />
      <ul className="route-summary-levels">
        {RISK_LABELS.map((label, level) => (
          <li key={label}>
            <span className="dot" style={{ background: riskColor(level as RiskLevel) }} /> {label}{' '}
            <b>{route.risk_miles[label]} mi</b>
          </li>
        ))}
      </ul>

      <p className="route-summary-why">
        {isRecommended
          ? plan.recommendation_reasons.length
            ? 'Recommended: ' + plan.recommendation_reasons.join('; ')
            : 'Recommended.'
          : route.why_not_recommended}
      </p>
    </div>
  )
}
