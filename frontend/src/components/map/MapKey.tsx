import { riskColor } from '../../lib/risk'

/** Collapsible legend for the map symbols. */
export default function MapKey() {
  return (
    <details className="map-key" open>
      <summary>Map key</summary>
      <ul>
        <li>
          <span className="key-line selected" style={{ background: riskColor(0) }} /> Recommended route, coloured by
          risk
        </li>
        <li>
          <span className="key-line" /> Other routes: grey where risk is Low (click one to select it)
        </li>
        <li>
          <span className="key-dot" style={{ background: riskColor(2) }} /> Weather checkpoint (click for details)
        </li>
        <li>
          <span className="key-pin start">Start</span>
          <span className="key-pin end">End</span> Trip start and destination
        </li>
        <li>
          <span className="key-truck">A</span> Truck position at the slider time
        </li>
      </ul>
    </details>
  )
}
