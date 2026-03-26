import { type FormEvent, Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../../../api'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'

type SearchHit = {
  id: string
  type: 'product' | 'asset' | 'content' | 'knowledge' | 'user'
  label: string
  subtitle: string | null
  to: string
}

type SearchGroup = {
  key: string
  label: string
  hits: SearchHit[]
}

function normalize(value: string): string {
  return value.trim().toLowerCase()
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function asString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function asNullableString(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null
}

function parseSearchGroups(input: unknown): SearchGroup[] {
  if (!isRecord(input) || !Array.isArray(input.groups)) return []
  return input.groups
    .map(group => {
      const src = isRecord(group) ? group : {}
      const key = asString(src.type)
      const label = asString(src.label)
      const hits = Array.isArray(src.hits)
        ? src.hits
            .map(hit => {
              const item = isRecord(hit) ? hit : {}
              const id = asString(item.id)
              const type = asString(item.type)
              const title = asString(item.title)
              const detailPath = asString(item.detail_path)
              if (!id || !title || !detailPath) return null
              if (!['product', 'asset', 'content', 'knowledge', 'user'].includes(type)) return null
              return {
                id,
                type: type as SearchHit['type'],
                label: title,
                subtitle: asNullableString(item.subtitle),
                to: detailPath,
              } satisfies SearchHit
            })
            .filter((hit): hit is SearchHit => Boolean(hit))
        : []
      if (!key || !label || !hits.length) return null
      return { key, label, hits } satisfies SearchGroup
    })
    .filter((group): group is SearchGroup => Boolean(group))
}

function highlightText(text: string, query: string): Array<{ text: string; match: boolean }> {
  const q = normalize(query)
  if (!q) return [{ text, match: false }]
  const lower = text.toLowerCase()
  const parts: Array<{ text: string; match: boolean }> = []
  let cursor = 0
  while (cursor < text.length) {
    const index = lower.indexOf(q, cursor)
    if (index === -1) {
      parts.push({ text: text.slice(cursor), match: false })
      break
    }
    if (index > cursor) {
      parts.push({ text: text.slice(cursor, index), match: false })
    }
    parts.push({ text: text.slice(index, index + q.length), match: true })
    cursor = index + q.length
  }
  return parts.length ? parts : [{ text, match: false }]
}

function HighlightedText({ text, query }: { text: string; query: string }) {
  return (
    <>
      {highlightText(text, query).map((part, index) =>
        part.match ? (
          <mark key={`${part.text}-${index}`} className="topbar-search-mark">
            {part.text}
          </mark>
        ) : (
          <Fragment key={`${part.text}-${index}`}>{part.text}</Fragment>
        )
      )}
    </>
  )
}

export default function TopBar({ menuOpen = false, onToggleMenu }: { menuOpen?: boolean; onToggleMenu: () => void }) {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [groups, setGroups] = useState<SearchGroup[]>([])
  const [activeKey, setActiveKey] = useState<string | null>(null)
  const debouncedQuery = useDebouncedValue(query, 220)

  useEffect(() => {
    const q = normalize(debouncedQuery)
    if (q.length < 2) {
      setGroups([])
      setActiveKey(null)
      return
    }

    let active = true

    ;(async () => {
      setLoading(true)
      try {
        const response = await apiFetch<unknown>(`/search?q=${encodeURIComponent(q)}&per_type=4`)
        if (!active) return
        const parsedGroups = parseSearchGroups(response)
        setGroups(parsedGroups)
        const firstHit = parsedGroups[0]?.hits[0]
        setActiveKey(firstHit ? `${firstHit.type}:${firstHit.id}` : null)
      } catch {
        if (!active) return
        setGroups([])
        setActiveKey(null)
      } finally {
        if (active) setLoading(false)
      }
    })()

    return () => {
      active = false
    }
  }, [debouncedQuery])

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        inputRef.current?.focus()
        setOpen(true)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  const flatHits = useMemo(() => groups.flatMap(group => group.hits), [groups])

  const activeIndex = useMemo(() => {
    if (!activeKey) return -1
    return flatHits.findIndex(hit => `${hit.type}:${hit.id}` === activeKey)
  }, [activeKey, flatHits])

  function goTo(path: string) {
    setOpen(false)
    setQuery('')
    navigate(path)
  }

  function onInputKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (!open && ['ArrowDown', 'ArrowUp'].includes(event.key)) {
      setOpen(true)
      return
    }
    if (event.key === 'Escape') {
      setOpen(false)
      return
    }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      if (!flatHits.length) return
      event.preventDefault()
      const direction = event.key === 'ArrowDown' ? 1 : -1
      const start = activeIndex < 0 ? (direction > 0 ? -1 : 0) : activeIndex
      const next = (start + direction + flatHits.length) % flatHits.length
      const hit = flatHits[next]
      setActiveKey(`${hit.type}:${hit.id}`)
      return
    }
    if (event.key === 'Enter' && flatHits.length) {
      event.preventDefault()
      const hit = activeIndex >= 0 ? flatHits[activeIndex] : flatHits[0]
      goTo(hit.to)
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (flatHits.length) {
      const hit = activeIndex >= 0 ? flatHits[activeIndex] : flatHits[0]
      goTo(hit.to)
      return
    }
    if (normalize(query)) {
      goTo('/operations')
    }
  }

  return (
    <header className="topbar" role="banner">
      <div className="topbar-inner">
        <button
          type="button"
          className="topbar-menu-btn"
          onClick={onToggleMenu}
          aria-label="Navigation öffnen"
          aria-controls="mobile-navigation-drawer"
          aria-expanded={menuOpen}
        >
          ☰
        </button>
        <div className="topbar-search-wrap">
          <form onSubmit={onSubmit} role="search" aria-label="Globale Suche">
            <label htmlFor="global-search" className="sr-only">Globale Suche</label>
            <input
              id="global-search"
              ref={inputRef}
              className="topbar-search"
              placeholder="Global suchen: Produkte, Assets, Content, Knowledge, Benutzer …"
              aria-label="Suchen"
              role="combobox"
              aria-autocomplete="list"
              aria-expanded={open && normalize(query).length > 0}
              aria-controls="global-search-results"
              aria-activedescendant={activeKey ? `search-option-${activeKey}` : undefined}
              value={query}
              onFocus={() => setOpen(true)}
              onKeyDown={onInputKeyDown}
              onBlur={() => {
                setTimeout(() => setOpen(false), 120)
              }}
              onChange={event => setQuery(event.target.value)}
            />
          </form>
          <div className="sr-only" aria-live="polite" aria-atomic="true">
            {loading ? 'Suche läuft' : groups.length ? `${flatHits.length} Suchtreffer verfügbar` : normalize(query) ? 'Keine Suchtreffer' : ''}
          </div>
          {open && normalize(query) && (
            <div id="global-search-results" className="topbar-search-results" role="listbox" aria-label="Suchergebnisse">
              {loading && <div className="topbar-search-empty">Suche läuft…</div>}
              {!loading && groups.length === 0 && (
                <div className="topbar-search-empty">Keine Treffer. Enter öffnet Operations Inbox.</div>
              )}
              {!loading &&
                groups.map(group => (
                  <div key={group.key} className="topbar-search-group">
                    <div className="topbar-search-group-title">{group.label}</div>
                    {group.hits.map(hit => {
                      const key = `${hit.type}:${hit.id}`
                      const active = key === activeKey
                      return (
                        <button
                          key={key}
                          id={`search-option-${key}`}
                          className={active ? 'topbar-search-item active' : 'topbar-search-item'}
                          onMouseDown={() => goTo(hit.to)}
                          onMouseEnter={() => setActiveKey(key)}
                          type="button"
                          role="option"
                          aria-selected={active}
                        >
                          <span className="topbar-search-item-main">
                            <HighlightedText text={hit.label} query={query} />
                          </span>
                          {hit.subtitle && (
                            <span className="topbar-search-item-sub muted small">
                              <HighlightedText text={hit.subtitle} query={query} />
                            </span>
                          )}
                        </button>
                      )
                    })}
                  </div>
                ))}
            </div>
          )}
        </div>
        <div className="topbar-right">
          <button type="button" className="topbar-icon-btn" aria-label="Benachrichtigungen">
            🔔
            <span className="badge">3</span>
          </button>
          <button type="button" className="topbar-icon-btn" aria-label="Nachrichten">
            ✉
            <span className="badge">7</span>
          </button>
          <button type="button" className="topbar-profile" aria-label="Profil öffnen">NH</button>
        </div>
      </div>
    </header>
  );
}
