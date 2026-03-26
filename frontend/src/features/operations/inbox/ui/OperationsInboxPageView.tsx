import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../../../api'
import { getErrorMessage } from '../../../../shared/lib/errors'
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
  asset_review: 'Asset-Review',
  registration_approval: 'Registrierungsfreigabe',
  email_risk: 'Riskanter E-Mail-Entwurf',
  content_overdue: 'Überfällige Content-Aufgabe',
}

const PRIORITY_LABELS: Record<OperationPriority, string> = {
  low: 'Niedrig',
  medium: 'Mittel',
  high: 'Hoch',
  critical: 'Kritisch',
}

function formatDateTime(value: string | null): string {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString('de-DE')
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
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<OperationInboxOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)

  const [userFilter, setUserFilter] = useState(searchParams.get('user') || 'all')
  const [roleFilter, setRoleFilter] = useState<'all' | OperationRole>((searchParams.get('role') as 'all' | OperationRole) || 'all')
  const [priorityFilter, setPriorityFilter] = useState<'all' | OperationPriority>((searchParams.get('priority') as 'all' | OperationPriority) || 'all')
  const [dueFilter, setDueFilter] = useState<DueFilter>((searchParams.get('due') as DueFilter) || 'all')
  const [pageSize, setPageSize] = useState(() => {
    const parsed = Number(searchParams.get('limit') || '50')
    if (![25, 50, 100].includes(parsed)) return 50
    return parsed
  })
  const [offset, setOffset] = useState(() => Math.max(0, Number(searchParams.get('offset') || '0') || 0))
  const tableAnchorRef = useRef<HTMLDivElement | null>(null)
  function changePage(direction: 'prev' | 'next') {
    setOffset(curr => {
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
      const response = await apiFetch<OperationInboxOut>(`/operations/inbox?limit=${pageSize}&offset=${offset}`)
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
    next.set('limit', String(pageSize))
    next.set('offset', String(offset))
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true })
    }
  }, [userFilter, roleFilter, priorityFilter, dueFilter, pageSize, offset, searchParams, setSearchParams])

  const allItems = data?.items ?? []

  const assigneeOptions = useMemo(() => {
    const values = new Set<string>()
    for (const item of allItems) {
      values.add(item.assignee_username || 'unassigned')
    }
    return Array.from(values).sort((a, b) => a.localeCompare(b, 'de'))
  }, [allItems])

  const filteredItems = useMemo(() => {
    return allItems.filter(item => {
      const assignee = item.assignee_username || 'unassigned'
      if (userFilter !== 'all' && assignee !== userFilter) return false
      if (roleFilter !== 'all' && item.responsible_role !== roleFilter) return false
      if (priorityFilter !== 'all' && item.priority !== priorityFilter) return false
      if (!matchesDueFilter(item, dueFilter)) return false
      return true
    })
  }, [allItems, userFilter, roleFilter, priorityFilter, dueFilter])

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
        title="Operations Inbox konnte nicht geladen werden"
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
          <h2>Operations Inbox</h2>
          <button className="btn" onClick={() => {
            void load()
          }}>
            Refresh
          </button>
        </div>
        <div className="muted">Zentrale Arbeitsoberfläche für offene Freigaben, ToDos und Eskalationen.</div>

        <div className="control-row mt16">
          <div className="card tight">
            <div className="muted small">Offen</div>
            <div className="kpi metric-kpi">{filteredItems.length}</div>
          </div>
          <div className="card tight">
            <div className="muted small">Kritisch</div>
            <div className="kpi metric-kpi">{prioritySummary.critical}</div>
          </div>
          <div className="card tight">
            <div className="muted small">Hoch</div>
            <div className="kpi metric-kpi">{prioritySummary.high}</div>
          </div>
          <div className="card tight">
            <div className="muted small">Eskaliert</div>
            <div className="kpi metric-kpi">{filteredItems.filter(item => item.escalation).length}</div>
          </div>
        </div>
      </section>

      <section className="card">
        <div className="card-head">
          <h3>Filter</h3>
        </div>
        <div className="control-row">
          <select value={userFilter} onChange={e => setUserFilter(e.target.value)}>
            <option value="all">Benutzer: Alle</option>
            {assigneeOptions.map(value => (
              <option key={value} value={value}>
                Benutzer: {value === 'unassigned' ? 'Nicht zugewiesen' : value}
              </option>
            ))}
          </select>

          <select value={roleFilter} onChange={e => setRoleFilter(e.target.value as 'all' | OperationRole)}>
            <option value="all">Rolle: Alle</option>
            <option value="admin">Rolle: Admin</option>
            <option value="editor">Rolle: Editor</option>
            <option value="viewer">Rolle: Viewer</option>
          </select>

          <select value={priorityFilter} onChange={e => setPriorityFilter(e.target.value as 'all' | OperationPriority)}>
            <option value="all">Priorität: Alle</option>
            <option value="low">Priorität: Niedrig</option>
            <option value="medium">Priorität: Mittel</option>
            <option value="high">Priorität: Hoch</option>
            <option value="critical">Priorität: Kritisch</option>
          </select>

          <select value={dueFilter} onChange={e => setDueFilter(e.target.value as DueFilter)}>
            <option value="all">Fälligkeit: Alle</option>
            <option value="overdue">Fälligkeit: Überfällig</option>
            <option value="today">Fälligkeit: Heute</option>
            <option value="next7">Fälligkeit: Nächste 7 Tage</option>
            <option value="none">Fälligkeit: Ohne Datum</option>
          </select>

          <select value={String(pageSize)} onChange={e => {
            setPageSize(Number(e.target.value))
            setOffset(0)
          }}>
            <option value="25">25 / Seite</option>
            <option value="50">50 / Seite</option>
            <option value="100">100 / Seite</option>
          </select>
        </div>
      </section>

      <section className="card">
        <div ref={tableAnchorRef} />
        <div className="card-head">
          <h3>Offene Freigaben & ToDos</h3>
        </div>
        <table className="status-table">
          <caption className="sr-only">Operations Inbox Einträge</caption>
          <thead>
            <tr>
              <th scope="col">Typ</th>
              <th scope="col">Titel</th>
              <th scope="col">Priorität</th>
              <th scope="col">Eskalation</th>
              <th scope="col">Zuständigkeit</th>
              <th scope="col">Fällig</th>
              <th scope="col">Aktion</th>
            </tr>
          </thead>
          <tbody>
            {filteredItems.map(item => (
              <tr key={item.id}>
                <td>{KIND_LABELS[item.kind]}</td>
                <td>
                  <div>{item.title}</div>
                  <div className="muted small">{item.description}</div>
                </td>
                <td>
                  <span className={`status-badge ${item.priority === 'critical' ? 'danger' : item.priority === 'high' ? 'warn' : 'ok'}`}>
                    {PRIORITY_LABELS[item.priority]}
                  </span>
                </td>
                <td>{item.escalation ? 'Ja' : 'Nein'}</td>
                <td>
                  <div>Rolle: {item.responsible_role}</div>
                  <div className="muted small">Benutzer: {item.assignee_username || 'Nicht zugewiesen'}</div>
                </td>
                <td>
                  <div>{formatDateTime(item.due_at)}</div>
                  {isOverdue(item.due_at) && <div className="muted small">überfällig</div>}
                </td>
                <td>
                  <Link className="btn" to={item.source_route}>Öffnen</Link>
                </td>
              </tr>
            ))}
            {filteredItems.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">Keine Einträge für die aktuelle Filterung.</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      <div className="row between">
        <button className="btn" onClick={() => changePage('prev')} disabled={offset <= 0}>← Zurück</button>
        <span className="muted small">Offset {offset} · Limit {pageSize} · Ergebnisse {filteredItems.length}</span>
        <button className="btn" onClick={() => changePage('next')} disabled={allItems.length < pageSize}>Weiter →</button>
      </div>
    </div>
  )
}
