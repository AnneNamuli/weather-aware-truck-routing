import { formatDateTime, formatInchesPerHour, formatMph } from '../../lib/format'
import { RISK_LABELS, riskColor } from '../../lib/risk'
import type { Checkpoint, Route } from '../../types'

/** Weather, risk and ETA at one checkpoint. */
export default function CheckpointPopup({ route, checkpoint }: { route: Route; checkpoint: Checkpoint }) {
  const row = (name: string, value: string, level: number) => (
    <tr>
      <th>{name}</th>
      <td>{value}</td>
      <td>
        <span className="dot" style={{ background: riskColor(level as Checkpoint['risk']) }} /> {RISK_LABELS[level]}
      </td>
    </tr>
  )
  return (
    <div className="cp-popup">
      <div className="cp-popup-head">
        <strong>
          Route {route.id} · mile {Math.round(checkpoint.mile)}
        </strong>
        <span className="risk-chip" style={{ '--risk': riskColor(checkpoint.risk) } as React.CSSProperties}>
          {checkpoint.risk_label}
        </span>
      </div>
      <div className="muted">ETA {formatDateTime(checkpoint.eta)}</div>
      {checkpoint.driver && (
        <div className="cp-driver">
          Driver: <b>{checkpoint.driver}</b>
        </div>
      )}
      <table>
        <tbody>
          {row(
            'Wind',
            `${formatMph(checkpoint.wind_mph)} mph (gust ${formatMph(checkpoint.gust_mph)})`,
            checkpoint.levels.wind,
          )}
          {row('Rain', `${formatInchesPerHour(checkpoint.rain_in_hr)} in/hr`, checkpoint.levels.rain)}
          {row('Snow', `${formatInchesPerHour(checkpoint.snow_in_hr)} in/hr`, checkpoint.levels.snow)}
        </tbody>
      </table>
      {checkpoint.load_note && <div className="load-note">Load rule: {checkpoint.load_note}</div>}
      <div className="muted small">Represents {checkpoint.covers_miles} mi of route</div>
    </div>
  )
}
