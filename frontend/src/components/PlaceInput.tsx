import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { geocode } from '../api'
import { parseCoords } from '../lib/place'
import type { Place } from '../types'

interface Props {
  label: string
  value: Place | null
  onChange: (place: Place | null) => void
  /** Lets the form look up typed text on submit when no suggestion was picked. */
  onTextChange: (text: string) => void
  placeholder?: string
}

const SEARCH_DEBOUNCE_MS = 250
// Long enough for a click on a suggestion to land before the list closes.
const CLOSE_AFTER_BLUR_MS = 120

/** Place field with debounced suggestions; also accepts "lat, lon". */
export default function PlaceInput({ label, value, onChange, onTextChange, placeholder }: Props) {
  const id = useId()
  const [text, setText] = useState(value?.label ?? '')
  const [results, setResults] = useState<Place[]>([])
  const [open, setOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(0)
  const [loading, setLoading] = useState(false)
  const typed = useRef(false)

  // Show the label when a place is set from outside (a sample trip), but don't wipe what
  // the user is typing when the place is cleared.
  const [prevValue, setPrevValue] = useState(value)
  if (value !== prevValue) {
    setPrevValue(value)
    if (value) setText(value.label)
  }

  const query = text.trim()
  const coordOption = useMemo(() => parseCoords(query), [query])
  const searchable = !coordOption && query.length >= 3
  const options = coordOption ? [coordOption] : searchable ? results : []

  useEffect(() => {
    if (!typed.current || !searchable) return
    const ctrl = new AbortController()
    const timer = setTimeout(() => {
      setLoading(true)
      geocode(query, ctrl.signal)
        .then((found) => {
          setResults(found)
          setHighlighted(0)
        })
        .catch(() => {})
        .finally(() => setLoading(false))
    }, SEARCH_DEBOUNCE_MS)
    return () => {
      clearTimeout(timer)
      ctrl.abort()
    }
  }, [query, searchable])

  const choose = (place: Place) => {
    typed.current = false
    onChange(place)
    setText(place.label)
    setOpen(false)
  }

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (!open || !options.length) return
    if (event.key === 'ArrowDown') setHighlighted((current) => (current + 1) % options.length)
    else if (event.key === 'ArrowUp') setHighlighted((current) => (current - 1 + options.length) % options.length)
    else if (event.key === 'Enter') choose(options[highlighted])
    else if (event.key === 'Escape') setOpen(false)
    else return
    event.preventDefault()
  }

  return (
    <div className="field place-input">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        value={text}
        placeholder={placeholder}
        autoComplete="off"
        role="combobox"
        aria-expanded={open && options.length > 0}
        aria-controls={`${id}-list`}
        onChange={(event) => {
          typed.current = true
          setText(event.target.value)
          onTextChange(event.target.value)
          setOpen(true)
          if (value) onChange(null)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), CLOSE_AFTER_BLUR_MS)}
        onKeyDown={onKeyDown}
      />
      {loading && <span className="spinner small input-spinner" aria-hidden />}
      {open && options.length > 0 && (
        <ul className="suggestions" id={`${id}-list`} role="listbox">
          {options.map((option, index) => (
            <li
              key={`${option.lat},${option.lon},${index}`}
              role="option"
              aria-selected={index === highlighted}
              className={index === highlighted ? 'active' : ''}
              onMouseDown={(event) => {
                event.preventDefault()
                choose(option)
              }}
              onMouseEnter={() => setHighlighted(index)}
            >
              {option.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
