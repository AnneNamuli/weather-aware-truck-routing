import type { HeatLayer, RiskLevel } from '../types'

export const RISK_LABELS = ['Low', 'Moderate', 'High', 'Severe', 'No Travel'] as const

export const RISK_RGB: [number, number, number][] = [
  [47, 158, 91], // Low
  [232, 181, 17], // Moderate
  [240, 123, 22], // High
  [214, 47, 60], // Severe
  [123, 44, 191], // No Travel
]

/** CSS colour for a risk level. */
export const riskColor = (level: RiskLevel) => `rgb(${RISK_RGB[level].join(',')})`

type Stop = [value: number, level: RiskLevel, alpha: number]

// Stops sit on the risk thresholds, so colours change where the risk level does.
// The "risk" layer comes from the backend because it includes the load rules.
const WIND: Stop[] = [
  [0, 0, 0],
  [15, 0, 0.18],
  [25, 1, 0.5],
  [35, 2, 0.58],
  [45, 3, 0.64],
  [55, 4, 0.72],
]
const RAMPS: Record<Exclude<HeatLayer, 'risk'>, Stop[]> = {
  wind: WIND,
  gust: WIND,
  rain: [
    [0, 0, 0],
    [0.02, 0, 0.22],
    [0.1, 1, 0.5],
    [0.25, 2, 0.58],
    [0.5, 3, 0.64],
    [1.0, 4, 0.72],
  ],
  snow: [
    [0, 0, 0],
    [0.05, 0, 0.22],
    [0.5, 1, 0.5],
    [1.0, 2, 0.58],
    [2.0, 3, 0.64],
    [3.0, 4, 0.72],
  ],
}
const RISK_ALPHA = [0.16, 0.5, 0.58, 0.64, 0.72]

type RGBA = [number, number, number, number]

/** RGBA for a heatmap cell, blended between the ramp's stops. */
export function heatColor(layer: HeatLayer, value: number): RGBA {
  if (layer === 'risk') {
    const [red, green, blue] = RISK_RGB[value]
    return [red, green, blue, RISK_ALPHA[value] * 255]
  }
  const stops = RAMPS[layer]
  const lastStop = stops[stops.length - 1]
  if (value >= lastStop[0]) {
    const [, level, alpha] = lastStop
    return [...RISK_RGB[level], alpha * 255]
  }
  let lower = 0
  while (value >= stops[lower + 1][0]) lower++
  const [fromValue, fromLevel, fromAlpha] = stops[lower]
  const [toValue, toLevel, toAlpha] = stops[lower + 1]
  const fraction = (value - fromValue) / (toValue - fromValue)
  const fromColor = RISK_RGB[fromLevel]
  const toColor = RISK_RGB[toLevel]
  const blend = (from: number, to: number) => from + (to - from) * fraction
  return [
    blend(fromColor[0], toColor[0]),
    blend(fromColor[1], toColor[1]),
    blend(fromColor[2], toColor[2]),
    blend(fromAlpha, toAlpha) * 255,
  ]
}

export const LAYER_INFO: Record<HeatLayer, { label: string; unit: string; ticks: string[] }> = {
  risk: { label: 'Risk (with load)', unit: '', ticks: [...RISK_LABELS] },
  wind: { label: 'Wind', unit: 'mph', ticks: ['<25', '25', '35', '45', '55+'] },
  gust: { label: 'Gusts', unit: 'mph', ticks: ['<25', '25', '35', '45', '55+'] },
  rain: { label: 'Rain', unit: 'in/hr', ticks: ['<.10', '.10', '.25', '.50', '>1'] },
  snow: { label: 'Snow', unit: 'in/hr', ticks: ['<.5', '.5', '1', '2', '>3'] },
}
