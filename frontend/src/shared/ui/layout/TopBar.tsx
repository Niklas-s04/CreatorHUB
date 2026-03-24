import { type FormEvent, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../../../api'
import { parseProductsDtoArray } from '../../api/validators'
import { NAV_SECTIONS_TASK_BASED } from '../../navigation/navConfig'

type SearchResult = {
  key: string
  label: string
  hint: string
  to: string
}

type ProductHit = {
  id: number
  title: string
}

function normalize(value: string): string {
  return value.trim().toLowerCase()
}

export default function TopBar({ onToggleMenu }: { onToggleMenu: () => void }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [productHits, setProductHits] = useState<ProductHit[]>([])

  const domainResults = useMemo(() => {
    const q = normalize(query)
    if (!q) return []

    const results: SearchResult[] = []
    for (const section of NAV_SECTIONS_TASK_BASED) {
      for (const item of section.items) {
        const haystack = `${item.label} ${item.keywords.join(' ')}`.toLowerCase()
        if (haystack.includes(q)) {
          results.push({
            key: `route:${item.to}`,
            label: item.label,
            hint: section.title,
            to: item.to,
          })
        }
      }
    }
    return results
  }, [query])

  useEffect(() => {
    const q = normalize(query)
    if (q.length < 2) {
      setProductHits([])
      return
    }

    const timer = setTimeout(async () => {
      try {
        const response = await apiFetch<unknown>(`/products?limit=8&q=${encodeURIComponent(q)}`)
        const rows = parseProductsDtoArray(response)
        setProductHits(
          rows
            .filter(row => row.id >= 0)
            .map(row => ({ id: row.id, title: row.title }))
            .slice(0, 8)
        )
      } catch {
        setProductHits([])
      }
    }, 220)

    return () => clearTimeout(timer)
  }, [query])

  const mergedResults = useMemo<SearchResult[]>(() => {
    const productResults = productHits.map(hit => ({
      key: `product:${hit.id}`,
      label: hit.title,
      hint: 'Produktdetail',
      to: `/products/${hit.id}`,
    }))
    return [...domainResults, ...productResults].slice(0, 12)
  }, [domainResults, productHits])

  function goTo(path: string) {
    setOpen(false)
    setQuery('')
    navigate(path)
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (mergedResults.length) {
      goTo(mergedResults[0].to)
      return
    }
    if (normalize(query)) {
      goTo('/operations')
    }
  }

  return (
    <div className="topbar">
      <div className="topbar-inner">
        <button className="topbar-menu-btn" onClick={onToggleMenu} aria-label="Navigation öffnen">☰</button>
        <div className="topbar-search-wrap">
          <form onSubmit={onSubmit}>
            <input
              className="topbar-search"
              placeholder="Suchen nach Aufgaben, Bereichen oder Produkten …"
              aria-label="Suchen"
              value={query}
              onFocus={() => setOpen(true)}
              onBlur={() => {
                setTimeout(() => setOpen(false), 120)
              }}
              onChange={event => setQuery(event.target.value)}
            />
          </form>
          {open && normalize(query) && (
            <div className="topbar-search-results" role="listbox" aria-label="Suchergebnisse">
              {mergedResults.length === 0 && (
                <div className="topbar-search-empty">Keine Treffer. Enter öffnet Operations Inbox.</div>
              )}
              {mergedResults.map(result => (
                <button
                  key={result.key}
                  className="topbar-search-item"
                  onMouseDown={() => goTo(result.to)}
                  type="button"
                >
                  <span>{result.label}</span>
                  <span className="muted small">{result.hint}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="topbar-right">
          <div className="topbar-icon-btn" aria-label="Benachrichtigungen">
            🔔
            <span className="badge">3</span>
          </div>
          <div className="topbar-icon-btn" aria-label="Nachrichten">
            ✉
            <span className="badge">7</span>
          </div>
          <div className="topbar-profile" aria-label="Profil">NH</div>
        </div>
      </div>
    </div>
  );
}
