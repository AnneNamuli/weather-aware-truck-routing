import { RISK_LABELS, riskColor } from '../lib/risk'
import type { RiskLevel, Route } from '../types'

/** Stacked bar of a route's miles at each risk level. */
export default function RiskBar({ route }: { route: Route }) {
  const totalMiles = route.distance_miles || 1
  return (
    <div
      className="risk-bar"
      role="img"
      aria-label={RISK_LABELS.map((label) => `${label} ${route.risk_miles[label]} miles`).join(', ')}
    >
      {RISK_LABELS.map((label, level) => {
        const miles = route.risk_miles[label]
        return miles > 0 ? (
          <span
            key={label}
            style={{ width: `${(miles / totalMiles) * 100}%`, background: riskColor(level as RiskLevel) }}
            title={`${label}: ${miles} mi`}
          />
        ) : null
      })}
    </div>
  )
}
