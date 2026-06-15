import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../../../api'
import { useI18n } from '../../../../shared/i18n/i18n'
import { getErrorMessage } from '../../../../shared/lib/errors'
import { useDebouncedValue } from '../../../../shared/hooks/useDebouncedValue'
import { ErrorState } from '../../../../shared/ui/states/ErrorState'
import { ListSkeleton } from '../../../../shared/ui/states/ListSkeleton'

type OperationKind = 'asset_review' | 'registration_approval' | 'email_risk' | 'content_overdue'
type OperationPriority = 'low' | 'medium' | 'high' | 'critical'
type OperationRole = 'admin' | 'editor' | 'viewer'
type DueFilter = 'all' | 'overdue' | 'today' | 'next7' | 'none'

type OperationInboxItem = {
  id: string
  kind: OperationKind
  title: string
  description: string
  source_route: string
  source_id: string
  priority: OperationPriority
  escalation: boolean
  due_at: string | null
  created_at: string | null
  updated_at: string | null
  assignee_username: string | null
  responsible_role: OperationRole
}

type OperationInboxOut = {
  generated_at: string
  total_open: number
  items: OperationInboxItem[]
}

const KIND_LABELS: Record<OperationKind, string> = {
  asset_review: 'Asset review',
  registration_approval: 'Registration approval',
  email_risk: 'Risky email draft',
  content_overdue: 'Overdue content task',
}

const PRIORITY_LABELS: Record<OperationPriority, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  critical: 'Critical',
}

function formatDateTime(value: string | null, locale: 'de-DE' | 'en-US'): string {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString(locale)
  } catch {
    return value
  }
}

function isOverdue(value: string | null): boolean {
  if (!value) return false
  const due = new Date(value)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return due < today
}

function matchesDueFilter(item: OperationInboxItem, dueFilter: DueFilter): boolean {
  if (dueFilter === 'all') return true
  if (dueFilter === 'none') return !item.due_at
  if (!item.due_at) return false

  const due = new Date(item.due_at)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const dueDay = new Date(due)
  dueDay.setHours(0, 0, 0, 0)

  if (dueFilter === 'overdue') {
    return dueDay < today
  }
  if (dueFilter === 'today') {
    return dueDay.getTime() === today.getTime()
  }
  if (dueFilter === 'next7') {
    const next7 = new Date(today)
    next7.setDate(today.getDate() + 7)
    return dueDay >= today && dueDay <= next7
  }
  return true
}

export default function OperationsInboxPageView() {
  const { language } = useI18n()
  const isEnglish = language === 'en'
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<OperationInboxOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [searchInput, setSearchInput] = useState(searchParams.get('q') || '')

  const [userFilter, setUserFilter] = useState(searchParams.get('user') || 'all')
  const [roleFilter, setRoleFilter] = useState<'all' | OperationRole>(
    (searchParams.get('role') as 'all' | OperationRole) || 'all'
  )
  const [priorityFilter, setPriorityFilter] = useState<'all' | OperationPriority>(
    (searchParams.get('priority') as 'all' | OperationPriority) || 'all'
  )
  const [dueFilter, setDueFilter] = useState<DueFilter>(
    (searchParams.get('due') as DueFilter) || 'all'
  )
  const [pageSize, setPageSize] = useState(() => {
    const parsed = Number(searchParams.get('limit') || '50')
    if (![25, 50, 100].includes(parsed)) return 50
    return parsed
  })
  const [offset, setOffset] = useState(() =>
    Math.max(0, Number(searchParams.get('offset') || '0') || 0)
  )
  const debouncedSearch = useDebouncedValue(searchInput.trim().toLowerCase(), 250)
  const tableAnchorRef = useRef<HTMLDivElement | null>(null)
  function changePage(direction: 'prev' | 'next') {
    setOffset((curr) => {
      if (direction === 'prev') return Math.max(0, curr - pageSize)
      if (allItems.length < pageSize) return curr
      return curr + pageSize
    })
    tableAnchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  async function load() {
    try {
      setErr(null)
      setLoading(true)
      const response = await apiFetch<OperationInboxOut>(
        `/operations/inbox?limit=${pageSize}&offset=${offset}`
      )
      setData(response)
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [pageSize, offset])

  useEffect(() => {
    setOffset(0)
  }, [userFilter, roleFilter, priorityFilter, dueFilter, pageSize])

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    if (userFilter !== 'all') next.set('user', userFilter)
    else next.delete('user')
    if (roleFilter !== 'all') next.set('role', roleFilter)
    else next.delete('role')
    if (priorityFilter !== 'all') next.set('priority', priorityFilter)
    else next.delete('priority')
    if (dueFilter !== 'all') next.set('due', dueFilter)
    else next.delete('due')
    if (debouncedSearch) next.set('q', debouncedSearch)
    else next.delete('q')
    next.set('limit', String(pageSize))
    next.set('offset', String(offset))
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true })
    }
  }, [
    userFilter,
    roleFilter,
    priorityFilter,
    dueFilter,
    debouncedSearch,
    pageSize,
    offset,
    searchParams,
    setSearchParams,
  ])

  const allItems = data?.items ?? []

  const assigneeOptions = useMemo(() => {
    const values = new Set<string>()
    for (const item of allItems) {
      values.add(item.assignee_username || 'unassigned')
    }
    return Array.from(values).sort((a, b) => a.localeCompare(b, 'de'))
  }, [allItems])

  const filteredItems = useMemo(() => {
    return allItems.filter((item) => {
      const assignee = item.assignee_username || 'unassigned'
      if (userFilter !== 'all' && assignee !== userFilter) return false
      if (roleFilter !== 'all' && item.responsible_role !== roleFilter) return false
      if (priorityFilter !== 'all' && item.priority !== priorityFilter) return false
      if (!matchesDueFilter(item, dueFilter)) return false
      if (debouncedSearch) {
        const haystack =
          `${item.title} ${item.description} ${item.assignee_username || ''} ${item.kind}`.toLowerCase()
        if (!haystack.includes(debouncedSearch)) return false
      }
      return true
    })
  }, [allItems, userFilter, roleFilter, priorityFilter, dueFilter, debouncedSearch])

  const prioritySummary = useMemo(() => {
    return filteredItems.reduce(
      (acc, item) => {
        acc[item.priority] += 1
        return acc
      },
      { low: 0, medium: 0, high: 0, critical: 0 } as Record<OperationPriority, number>
    )
  }, [filteredItems])

  if (loading) {
    return <ListSkeleton rows={8} />
  }

  if (err) {
    return (
      <ErrorState
        title={
          isEnglish
            ? 'Operations inbox could not be loaded'
            : 'Operations Inbox konnte nicht geladen werden'
        }
        message={err}
        onRetry={() => {
          void load()
        }}
      />
    )
  }

  return (
    <div className="container stack">
      <section className="card">
        <div className="card-head">
          <h2>{isEnglish ? 'Operations inbox' : 'Operations Inbox'}</h2>
          <button
            className="btn"
            onClick={() => {
              void load()
            }}
          >
            {isEnglish ? 'Refresh' : 'Aktualisieren'}
          </button>
        </div>
        <div className="muted">
          {isEnglish
            ? 'Central workspace for open approvals, todos and escalations.'
            : 'Zentrale Arbeitsoberfläche für offene Freigaben, ToDos und Eskalationen.'}
        </div>

        <div className="control-row mt16">
          <div className="card tight">
            <div className="muted small">{isEnglish ? 'Open' : 'Offen'}</div>
            <div className="kpi metric-kpi">{filteredItems.length}</div>
          </div>
          <div className="card tight">
            <div className="muted small">{isEnglish ? 'Critical' : 'Kritisch'}</div>
            <div className="kpi metric-kpi">{prioritySummary.critical}</div>
          </div>
          <div className="card tight">
            <div className="muted small">{isEnglish ? 'High' : 'Hoch'}</div>
            <div className="kpi metric-kpi">{prioritySummary.high}</div>
          </div>
          <div className="card tight">
            <div className="muted small">{isEnglish ? 'Escalated' : 'Eskaliert'}</div>
            <div className="kpi metric-kpi">
              {filteredItems.filter((item) => item.escalation).length}
            </div>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h3>{isEnglish ? 'Filters' : 'Filter'}</h3>
        </div>
        <div className="control-row">
          <input
            className="grow"
            placeholder={
              isEnglish
                ? 'Search (title, description, assignee, type)'
                : 'Suche (Titel, Beschreibung, Assignee, Typ)'
            }
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
          />

          <select value={userFilter} onChange={(e) => setUserFilter(e.target.value)}>
            <option value="all">{isEnglish ? 'User: all' : 'Benutzer: Alle'}</option>
            {assigneeOptions.map((value) => (
              <option key={value} value={value}>
                {isEnglish ? 'User' : 'Benutzer'}:{' '}
                {value === 'unassigned' ? (isEnglish ? 'Unassigned' : 'Nicht zugewiesen') : value}
              </option>
            ))}
          </select>

          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value as 'all' | OperationRole)}
          >
            <option value="all">{isEnglish ? 'Role: all' : 'Rolle: Alle'}</option>
            <option value="admin">{isEnglish ? 'Role: Admin' : 'Rolle: Admin'}</option>
            <option value="editor">{isEnglish ? 'Role: Editor' : 'Rolle: Editor'}</option>
            <option value="viewer">{isEnglish ? 'Role: Viewer' : 'Rolle: Viewer'}</option>
          </select>

          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value as 'all' | OperationPriority)}
          >
            <option value="all">{isEnglish ? 'Priority: all' : 'Priorität: Alle'}</option>
            <option value="low">{isEnglish ? 'Priority: low' : 'Priorität: Niedrig'}</option>
            <option value="medium">{isEnglish ? 'Priority: medium' : 'Priorität: Mittel'}</option>
            <option value="high">{isEnglish ? 'Priority: high' : 'Priorität: Hoch'}</option>
            <option value="critical">
              {isEnglish ? 'Priority: critical' : 'Priorität: Kritisch'}
            </option>
          </select>

          <select value={dueFilter} onChange={(e) => setDueFilter(e.target.value as DueFilter)}>
            <option value="all">{isEnglish ? 'Due date: all' : 'Fälligkeit: Alle'}</option>
            <option value="overdue">
              {isEnglish ? 'Due date: overdue' : 'Fälligkeit: Überfällig'}
            </option>
            <option value="today">{isEnglish ? 'Due date: today' : 'Fälligkeit: Heute'}</option>
            <option value="next7">
              {isEnglish ? 'Due date: next 7 days' : 'Fälligkeit: Nächste 7 Tage'}
            </option>
            <option value="none">{isEnglish ? 'Due date: none' : 'Fälligkeit: Ohne Datum'}</option>
          </select>

          <select
            value={String(pageSize)}
            onChange={(e) => {
              setPageSize(Number(e.target.value))
              setOffset(0)
            }}
          >
            <option value="25">25 {isEnglish ? '/ page' : '/ Seite'}</option>
            <option value="50">50 {isEnglish ? '/ page' : '/ Seite'}</option>
            <option value="100">100 {isEnglish ? '/ page' : '/ Seite'}</option>
          </select>
        </div>
      </section>

      <section className="card">
        <div ref={tableAnchorRef} />
        <div className="card-head">
          <h3>{isEnglish ? 'Open approvals & todos' : 'Offene Freigaben & ToDos'}</h3>
        </div>
        <table className="status-table">
          <caption className="sr-only">
            {isEnglish ? 'Operations inbox entries' : 'Operations Inbox Einträge'}
          </caption>
          <thead>
            <tr>
              <th scope="col">{isEnglish ? 'Type' : 'Typ'}</th>
              <th scope="col">{isEnglish ? 'Title' : 'Titel'}</th>
              <th scope="col">{isEnglish ? 'Priority' : 'Priorität'}</th>
              <th scope="col">{isEnglish ? 'Escalation' : 'Eskalation'}</th>
              <th scope="col">{isEnglish ? 'Ownership' : 'Zuständigkeit'}</th>
              <th scope="col">{isEnglish ? 'Due' : 'Fällig'}</th>
              <th scope="col">{isEnglish ? 'Action' : 'Aktion'}</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map((item) => (
              <tr key={item.id}>
                <td>{KIND_LABELS[item.kind]}</td>
                <td>
                  <div>{item.title}</div>
                  <div className="muted small">{item.description}</div>
                </td>
                <td>
                  <span
                    className={`status-badge ${item.priority === 'critical' ? 'danger' : item.priority === 'high' ? 'warn' : 'ok'}`}
                  >
                    {PRIORITY_LABELS[item.priority]}
                  </span>
                </td>
                <td>{item.escalation ? 'Ja' : 'Nein'}</td>
                <td>
                  <div>
                    {isEnglish ? 'Role' : 'Rolle'}: {item.responsible_role}
                  </div>
                  <div className="muted small">
                    {isEnglish ? 'User' : 'Benutzer'}:{' '}
                    {item.assignee_username || (isEnglish ? 'Unassigned' : 'Nicht zugewiesen')}
                  </div>
                </td>
                <td>
                  <div>{formatDateTime(item.due_at, isEnglish ? 'en-US' : 'de-DE')}</div>
                  {isOverdue(item.due_at) && (
                    <div className="muted small">{isEnglish ? 'overdue' : 'überfällig'}</div>
                  )}
                </td>
                <td>
                  <Link className="btn" to={item.source_route}>
                    {isEnglish ? 'Open' : 'Öffnen'}
                  </Link>
                </td>
              </tr>
            ))}
            {filteredItems.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
                  {isEnglish
                    ? 'No entries match the current filters.'
                    : 'Keine Einträge für die aktuelle Filterung.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      <div className="row between">
        <button className="btn" onClick={() => changePage('prev')} disabled={offset <= 0}>
          {isEnglish ? '← Back' : '← Zurück'}
        </button>
        <span className="muted small">
          {isEnglish ? 'Offset' : 'Offset'} {offset} · {isEnglish ? 'Limit' : 'Limit'} {pageSize} ·{' '}
          {isEnglish ? 'Results' : 'Ergebnisse'} {filteredItems.length}
        </span>
        <button
          className="btn"
          onClick={() => changePage('next')}
          disabled={allItems.length < pageSize}
        >
          {isEnglish ? 'Next →' : 'Weiter →'}
        </button>
      </div>
    </div>
  )
}
