import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { apiFetch } from '../../../../api'
import { useI18n } from '../../../../shared/i18n/i18n'
import { getErrorMessage } from '../../../../shared/lib/errors'
import { useDebouncedValue } from '../../../../shared/hooks/useDebouncedValue'
import { ErrorState } from '../../../../shared/ui/states/ErrorState'
import { ListSkeleton } from '../../../../shared/ui/states/ListSkeleton'

type OperationKind =
  | 'asset_review'
  | 'registration_approval'
  | 'email_risk'
  | 'content_overdue'
  | 'deal_checklist'
  | 'workflow_gap'
type OperationPriority = 'low' | 'medium' | 'high' | 'critical'
type OperationRole = 'admin' | 'editor' | 'viewer'
type DueFilter = 'all' | 'overdue' | 'today' | 'next7' | 'none'

const OPERATION_ROLES = ['admin', 'editor', 'viewer'] as const
const OPERATION_PRIORITIES = ['low', 'medium', 'high', 'critical'] as const
const DUE_FILTERS = ['overdue', 'today', 'next7', 'none'] as const

function enumFilterFromQuery<T extends string>(
  value: string | null,
  allowed: readonly T[]
): T | 'all' {
  return value && allowed.includes(value as T) ? (value as T) : 'all'
}

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
  deal_checklist: 'Incomplete deal checklist',
  workflow_gap: 'Workflow gap',
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

export default function OperationsInboxPageView() {
  const { language } = useI18n()
  const isEnglish = language === 'en'
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<OperationInboxOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [searchInput, setSearchInput] = useState((searchParams.get('q') || '').slice(0, 200))

  const [userFilter, setUserFilter] = useState(searchParams.get('user') || 'all')
  const [roleFilter, setRoleFilter] = useState<'all' | OperationRole>(
    enumFilterFromQuery(searchParams.get('role'), OPERATION_ROLES)
  )
  const [priorityFilter, setPriorityFilter] = useState<'all' | OperationPriority>(
    enumFilterFromQuery(searchParams.get('priority'), OPERATION_PRIORITIES)
  )
  const [dueFilter, setDueFilter] = useState<DueFilter>(
    enumFilterFromQuery(searchParams.get('due'), DUE_FILTERS)
  )
  const [pageSize, setPageSize] = useState(() => {
    const parsed = Number(searchParams.get('limit') || '50')
    if (![25, 50, 100].includes(parsed)) return 50
    return parsed
  })
  const [offset, setOffset] = useState(() => {
    const parsed = Number(searchParams.get('offset') || '0')
    return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : 0
  })
  const debouncedSearch = useDebouncedValue(searchInput.trim().toLowerCase(), 250)
  const tableAnchorRef = useRef<HTMLDivElement | null>(null)
  const requestSequenceRef = useRef(0)
  function changePage(direction: 'prev' | 'next') {
    setOffset((curr) => {
      if (direction === 'prev') return Math.max(0, curr - pageSize)
      if (allItems.length < pageSize) return curr
      return curr + pageSize
    })
    tableAnchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const load = useCallback(async () => {
    const requestSequence = ++requestSequenceRef.current
    try {
      setErr(null)
      setLoading(true)
      const query = new URLSearchParams({
        limit: String(pageSize),
        offset: String(offset),
      })
      if (userFilter !== 'all') query.set('assignee_user', userFilter)
      if (roleFilter !== 'all') query.set('role', roleFilter)
      if (priorityFilter !== 'all') query.set('priority', priorityFilter)
      if (dueFilter !== 'all') query.set('due', dueFilter)
      if (debouncedSearch) query.set('q', debouncedSearch)

      const response = await apiFetch<OperationInboxOut>(`/operations/inbox?${query.toString()}`)
      if (requestSequence !== requestSequenceRef.current) return
      setData(response)
    } catch (e: unknown) {
      if (requestSequence !== requestSequenceRef.current) return
      setErr(getErrorMessage(e))
    } finally {
      if (requestSequence === requestSequenceRef.current) {
        setLoading(false)
      }
    }
  }, [debouncedSearch, dueFilter, offset, pageSize, priorityFilter, roleFilter, userFilter])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    setOffset(0)
  }, [userFilter, roleFilter, priorityFilter, dueFilter, debouncedSearch, pageSize])

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

  const allItems = useMemo(() => data?.items ?? [], [data?.items])

  const assigneeOptions = useMemo(() => {
    const values = new Set<string>()
    for (const item of allItems) {
      values.add(item.assignee_username || 'unassigned')
    }
    return Array.from(values).sort((a, b) => a.localeCompare(b, 'de'))
  }, [allItems])

  const filteredItems = allItems

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
            <div className="kpi metric-kpi">{data?.total_open ?? 0}</div>
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
            maxLength={200}
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
          disabled={offset + allItems.length >= (data?.total_open ?? 0)}
        >
          {isEnglish ? 'Next →' : 'Weiter →'}
        </button>
      </div>
    </div>
  )
}
