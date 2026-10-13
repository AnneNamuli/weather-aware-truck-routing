import L from 'leaflet'
import { useEffect, useMemo, useRef } from 'react'
import { useMap } from 'react-leaflet'
import { heatColor } from '../../lib/risk'
import type { HeatLayer, Heatmap } from '../../types'

const BYTES_PER_PIXEL = 4 // RGBA

const mercY = (lat: number) => (Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360)) * 180) / Math.PI

interface Props {
  data: Heatmap
  layer: HeatLayer
  hour: number
  pane: string
  onHover: (value: number | null) => void
}

/**
 * Draws one hour into an nx x ny canvas (one pixel per cell) stretched over the grid bounds.
 * The browser's image scaling does the smoothing, and a slider step only rewrites ~200 pixels.
 */
export default function HeatmapOverlay({ data, layer, hour, pane, onHover }: Props) {
  const map = useMap()
  const heat = useRef<{ overlay: L.ImageOverlay; canvas: HTMLCanvasElement } | null>(null)

  const grid = useMemo(() => {
    const [[south, west], [north, east]] = data.bounds
    const valueIndexByCell = new Map<number, number>()
    data.cells.forEach((cell, valueIndex) => valueIndexByCell.set(cell, valueIndex))
    return { west, east, top: mercY(north), bottom: mercY(south), valueIndexByCell }
  }, [data])

  useEffect(() => {
    const canvas = document.createElement('canvas')
    canvas.width = data.nx
    canvas.height = data.ny
    const overlay = L.imageOverlay(canvas.toDataURL(), data.bounds, {
      pane,
      interactive: false,
      className: 'heat-overlay',
    }).addTo(map)
    heat.current = { overlay, canvas }
    return () => {
      overlay.remove()
      heat.current = null
    }
  }, [data, map, pane])

  useEffect(() => {
    if (!heat.current) return
    const { overlay, canvas } = heat.current
    const context = canvas.getContext('2d')
    if (!context) return
    const image = context.createImageData(data.nx, data.ny)
    const values = data.layers[layer][hour]
    data.cells.forEach((cell, valueIndex) => {
      const [red, green, blue, alpha] = heatColor(layer, values[valueIndex])
      const pixelOffset = cell * BYTES_PER_PIXEL
      image.data[pixelOffset] = red
      image.data[pixelOffset + 1] = green
      image.data[pixelOffset + 2] = blue
      image.data[pixelOffset + 3] = alpha
    })
    context.putImageData(image, 0, 0)
    overlay.setUrl(canvas.toDataURL())
  }, [data, layer, hour])

  useEffect(() => {
    const values = data.layers[layer][hour]
    const showValueUnderCursor = (event: L.LeafletMouseEvent) => {
      const col = Math.floor(((event.latlng.lng - grid.west) / (grid.east - grid.west)) * data.nx)
      const row = Math.floor(((grid.top - mercY(event.latlng.lat)) / (grid.top - grid.bottom)) * data.ny)
      const insideGrid = col >= 0 && col < data.nx && row >= 0 && row < data.ny
      const valueIndex = insideGrid ? grid.valueIndexByCell.get(row * data.nx + col) : undefined
      onHover(valueIndex === undefined ? null : values[valueIndex])
    }
    const clearValue = () => onHover(null)
    map.on('mousemove', showValueUnderCursor)
    map.on('mouseout', clearValue)
    return () => {
      map.off('mousemove', showValueUnderCursor)
      map.off('mouseout', clearValue)
    }
  }, [map, data, layer, hour, grid, onHover])

  return null
}
