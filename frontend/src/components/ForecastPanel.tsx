import { formatDateTime, formatInchesPerHour, formatMph } from '../lib/format'
import { LAYER_INFO, RISK_LABELS, RISK_RGB } from '../lib/risk'
import type { HeatLayer, Heatmap } from '../types'

const LAYERS: HeatLayer[] = ['risk', 'wind', 'gust', 'rain', 'snow']

interface Props {
  heatmap: Heatmap | null
  loading: boolean
  error: string | null
  onRetry: () => void
  layer: HeatLayer
  onLayer: (layer: HeatLayer) => void
  hour: number
  /** departure + hour */
  time: Date
  onHour: (hour: number) => void
  playing: boolean
  onPlaying: (playing: boolean) => void
  visible: boolean
  onVisible: (visible: boolean) => void
  hoverValue: number | null
}

/** Readout text for a heatmap value. */
function formatValue(layer: HeatLayer, value: number) {
  if (layer === 'risk') return RISK_LABELS[value]
  const { unit } = LAYER_INFO[layer]
  return layer === 'rain' || layer === 'snow' ? `${formatInchesPerHour(value)} ${unit}` : `${formatMph(value)} ${unit}`
}

/** Heatmap controls: layer, 0-48 h slider with play, legend and readout. */
export default function ForecastPanel(props: Props) {
  const info = LAYER_INFO[props.layer]
  const gradient = `linear-gradient(90deg, ${RISK_RGB.map((rgb) => `rgb(${rgb.join(',')})`).join(', ')})`

  return (
    <div className="forecast-panel" aria-label="Weather forecast heatmap">
      <div className="fp-row">
        <label className="toggle">
          <input type="checkbox" checked={props.visible} onChange={(event) => props.onVisible(event.target.checked)} />
          Heatmap
        </label>
        <div className="segmented small" role="radiogroup" aria-label="Heatmap layer">
          {LAYERS.map((layerOption) => (
            <button
              key={layerOption}
              type="button"
              role="radio"
              aria-checked={props.layer === layerOption}
              className={props.layer === layerOption ? 'on' : ''}
              onClick={() => props.onLayer(layerOption)}
            >
              {LAYER_INFO[layerOption].label.replace(' (with load)', '')}
            </button>
          ))}
        </div>
        <div className="fp-readout" aria-live="off">
          {props.hoverValue !== null && props.heatmap ? (
            <>
              Under cursor: <b>{formatValue(props.layer, props.hoverValue)}</b>
            </>
          ) : (
            <span className="muted">{info.label}</span>
          )}
        </div>
      </div>

      {props.loading && (
        <div className="fp-status">
          <span className="spinner small" aria-hidden /> Loading forecast…
        </div>
      )}
      {props.error && !props.loading && (
        <div className="fp-status error">
          Heatmap unavailable: {props.error}{' '}
          <button className="link" onClick={props.onRetry}>
            Retry
          </button>
        </div>
      )}

      {props.heatmap && (
        <>
          <div className="fp-row slider-row">
            <button
              className="play"
              onClick={() => props.onPlaying(!props.playing)}
              aria-label={props.playing ? 'Pause' : 'Play'}
            >
              {props.playing ? '❚❚' : '▶'}
            </button>
            <input
              type="range"
              min={0}
              max={props.heatmap.hours}
              step={1}
              value={props.hour}
              onChange={(event) => {
                props.onPlaying(false)
                props.onHour(Number(event.target.value))
              }}
              aria-label="Hours from departure"
              aria-valuetext={`+${props.hour} hours, ${formatDateTime(props.time)}`}
            />
            <div className="fp-time">
              <b>+{props.hour}h from departure</b>
              <span>{formatDateTime(props.time)}</span>
            </div>
          </div>
          <div className="legend">
            <div className="legend-bar" style={{ background: gradient }} />
            <div className="legend-ticks">
              {info.ticks.map((tick) => (
                <span key={tick}>{tick}</span>
              ))}
            </div>
            {info.unit && <span className="legend-unit">{info.unit}</span>}
          </div>
        </>
      )}
    </div>
  )
}
