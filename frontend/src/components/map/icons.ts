import L from 'leaflet'

/** Start/end pin: a dot on the point and a label above it. */
export function endpointIcon(kind: 'start' | 'end', place: string) {
  const root = document.createElement('div')
  root.className = `endpoint endpoint-${kind}`
  const label = document.createElement('div')
  label.className = 'endpoint-label'
  const tag = document.createElement('b')
  tag.textContent = kind === 'start' ? 'Start' : 'End'
  const name = document.createElement('span')
  name.textContent = place.split(',')[0] // textContent: the name comes from the geocoder
  name.title = place
  label.append(tag, name)
  const dot = document.createElement('div')
  dot.className = 'endpoint-dot'
  root.append(label, dot)
  return L.divIcon({ className: '', html: root, iconSize: [0, 0], iconAnchor: [0, 0] })
}

/** Round badge with the route letter, for the truck position. */
export function truckIcon(id: string, selected: boolean) {
  return L.divIcon({
    className: '',
    html: `<div class="truck${selected ? ' selected' : ''}">${id}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  })
}
