import { useCallback, useEffect, useState } from 'react'
import { apiFetch, apiUrl } from '../../../../api'
import { useI18n } from '../../../../shared/i18n/i18n'
import { useAuthz } from '../../../../shared/hooks/useAuthz'
import { getErrorMessage } from '../../../../shared/lib/errors'
import { ErrorState } from '../../../../shared/ui/states/ErrorState'
import { ListSkeleton } from '../../../../shared/ui/states/ListSkeleton'

type AuditEntry = {
  id: string
  action: string
  entity_type: string
  entity_id: string | null
  description: string | null
  actor_name: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  meta: Record<string, unknown> | null
  category: string
  critical: boolean
  created_at: string
}

type PageLike<T> = {
  items: T[]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function parseAuditEntries(input: unknown): AuditEntry[] {
  if (!isRecord(input)) return []
  const items = input.items
  if (!Array.isArray(items)) return []

  return items
    .map((item) => {
      if (!isRecord(item)) return null
      return {
        id: typeof item.id === 'string' ? item.id : '',
        action: typeof item.action === 'string' ? item.action : 'unknown',
        entity_type: typeof item.entity_type === 'string' ? item.entity_type : 'unknown',
        entity_id: typeof item.entity_id === 'string' ? item.entity_id : null,
        description: typeof item.description === 'string' ? item.description : null,
        actor_name: typeof item.actor_name === 'string' ? item.actor_name : null,
        before: isRecord(item.before) ? item.before : null,
        after: isRecord(item.after) ? item.after : null,
        meta: isRecord(item.meta) ? item.meta : null,
        category:
          isRecord(item.meta) && typeof item.meta.audit_category === 'string'
            ? item.meta.audit_category
            : inferCategory(typeof item.action === 'string' ? item.action : 'unknown'),
        critical: Boolean(isRecord(item.meta) ? item.meta.critical : false),
        created_at: typeof item.created_at === 'string' ? item.created_at : '',
      }
    })
    .filter((entry): entry is AuditEntry => Boolean(entry && entry.id))
}

function inferCategory(action: string): string {
  const normalized = action.toLowerCase()
  if (normalized.endsWith('.approval') || normalized.includes('.approval.')) return 'approval'
  if (normalized.startsWith('registration.request')) return 'approval'
  if (normalized.startsWith('user.role') || normalized.startsWith('user.permission')) {
    return 'permission_change'
  }
  if (
    normalized.startsWith('auth.') ||
    normalized.includes('password') ||
    normalized.includes('mfa')
  ) {
    return 'security'
  }
  if (normalized.startsWith('email.ai_settings') || normalized.startsWith('email.draft.')) {
    return 'ai_action'
  }
  return 'domain'
}

function prettyJson(data: unknown): string {
  try {
    return JSON.stringify(data ?? {}, null, 2)
  } catch {
    return String(data)
  }
}

function formatDate(value: string): string {
  try {
    return new Date(value).toLocaleString('de-DE')
  } catch {
    return value
  }
}

export default function AuditLogsPageView() {
  const { language } = useI18n()
  const isEnglish = language === 'en'
  const { hasPermission, loading: authzLoading } = useAuthz()
  const canViewAudit = hasPermission('audit.view')

  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [limit, setLimit] = useState(25)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)
  const [actionFilter, setActionFilter] = useState('')
  const [entityTypeFilter, setEntityTypeFilter] = useState('')
  const [actorFilter, setActorFilter] = useState('')
  const [searchFilter, setSearchFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [criticalOnly, setCriticalOnly] = useState(false)

  const load = useCallback(async () => {
    if (!canViewAudit) {
      setEntries([])
      setLoading(false)
      return
    }

    try {
      setErr(null)
      setLoading(true)
      const params = new URLSearchParams()
      params.set('limit', String(limit))
      params.set('offset', String(offset))
      params.set('sort_by', 'created_at')
      params.set('sort_order', 'desc')
      if (actionFilter.trim()) params.set('action', actionFilter.trim())
      if (entityTypeFilter.trim()) params.set('entity_type', entityTypeFilter.trim())
      if (actorFilter.trim()) params.set('actor', actorFilter.trim())
      if (searchFilter.trim()) params.set('search', searchFilter.trim())
      if (categoryFilter) params.set('category', categoryFilter)
      if (criticalOnly) params.set('critical_only', 'true')
      const response = await apiFetch<PageLike<AuditEntry> & { meta?: { total?: number } }>(
        `/audit?${params.toString()}`
      )
      const parsed = parseAuditEntries(response)
      setEntries(parsed)
      setTotal(typeof response.meta?.total === 'number' ? response.meta.total : parsed.length)
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [
    actionFilter,
    actorFilter,
    canViewAudit,
    categoryFilter,
    criticalOnly,
    entityTypeFilter,
    limit,
    offset,
    searchFilter,
  ])

  useEffect(() => {
    if (authzLoading) return
    void load()
  }, [authzLoading, load])

  function resetFilters() {
    setActionFilter('')
    setEntityTypeFilter('')
    setActorFilter('')
    setSearchFilter('')
    setCategoryFilter('')
    setCriticalOnly(false)
    setOffset(0)
  }

  function handleExportCsv() {
    const params = new URLSearchParams()
    if (actionFilter.trim()) params.set('action', actionFilter.trim())
    if (entityTypeFilter.trim()) params.set('entity_type', entityTypeFilter.trim())
    if (actorFilter.trim()) params.set('actor', actorFilter.trim())
    if (searchFilter.trim()) params.set('search', searchFilter.trim())
    if (categoryFilter) params.set('category', categoryFilter)
    if (criticalOnly) params.set('critical_only', 'true')
    const query = params.toString()
    const url = apiUrl(`/audit/export/csv${query ? `?${query}` : ''}`)
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  if (authzLoading || loading) {
    return <ListSkeleton rows={8} />
  }

  if (!canViewAudit) {
    return (
      <div className="card">
        <h2>{isEnglish ? 'Audit' : 'Audit'}</h2>
        <div className="muted">
          {isEnglish ? 'No permission for audit logs.' : 'Keine Berechtigung für Audit-Logs.'}
        </div>
      </div>
    )
  }

  if (err) {
    return (
      <ErrorState
        title={
          isEnglish ? 'Audit logs could not be loaded' : 'Audit-Logs konnten nicht geladen werden'
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
      <div className="card">
        <div className="card-head">
          <h2>{isEnglish ? 'Audit logs' : 'Audit-Logs'}</h2>
          <div className="control-row">
            <select
              value={String(limit)}
              onChange={(event) => {
                setLimit(Number(event.target.value))
                setOffset(0)
              }}
            >
              <option value="25">25 {isEnglish ? '/ page' : '/ Seite'}</option>
              <option value="50">50 {isEnglish ? '/ page' : '/ Seite'}</option>
            </select>
            <button
              className="btn"
              onClick={() => {
                void load()
              }}
            >
              {isEnglish ? 'Refresh' : 'Aktualisieren'}
            </button>
            <button className="btn" onClick={handleExportCsv}>
              {isEnglish ? 'Export CSV' : 'CSV exportieren'}
            </button>
          </div>
        </div>
        <div
          className="audit-filters"
          role="region"
          aria-label={isEnglish ? 'Audit filters' : 'Audit Filter'}
        >
          <input
            value={actionFilter}
            onChange={(event) => {
              setActionFilter(event.target.value)
              setOffset(0)
            }}
            placeholder={isEnglish ? 'Action' : 'Aktion'}
            aria-label={isEnglish ? 'Filter action' : 'Filter Aktion'}
          />
          <input
            value={entityTypeFilter}
            onChange={(event) => {
              setEntityTypeFilter(event.target.value)
              setOffset(0)
            }}
            placeholder={isEnglish ? 'Object type' : 'Objekttyp'}
            aria-label={isEnglish ? 'Filter object type' : 'Filter Objekttyp'}
          />
          <input
            value={actorFilter}
            onChange={(event) => {
              setActorFilter(event.target.value)
              setOffset(0)
            }}
            placeholder={isEnglish ? 'Actor' : 'Akteur'}
            aria-label={isEnglish ? 'Filter actor' : 'Filter Akteur'}
          />
          <input
            value={searchFilter}
            onChange={(event) => {
              setSearchFilter(event.target.value)
              setOffset(0)
            }}
            placeholder={isEnglish ? 'Search' : 'Suche'}
            aria-label={isEnglish ? 'Audit search' : 'Audit Suche'}
          />
          <select
            value={categoryFilter}
            onChange={(event) => {
              setCategoryFilter(event.target.value)
              setOffset(0)
            }}
            aria-label={isEnglish ? 'Filter category' : 'Filter Kategorie'}
          >
            <option value="">{isEnglish ? 'All categories' : 'Alle Kategorien'}</option>
            <option value="approval">{isEnglish ? 'Approvals' : 'Freigaben'}</option>
            <option value="permission_change">
              {isEnglish ? 'Permission changes' : 'Rechteänderungen'}
            </option>
            <option value="security">Security</option>
            <option value="ai_action">{isEnglish ? 'AI actions' : 'AI-Aktionen'}</option>
            <option value="domain">Domain</option>
          </select>
          <label className="audit-checkbox">
            <input
              type="checkbox"
              checked={criticalOnly}
              onChange={(event) => {
                setCriticalOnly(event.target.checked)
                setOffset(0)
              }}
            />
            {isEnglish ? 'Critical only' : 'Nur kritisch'}
          </label>
          <button className="btn" onClick={resetFilters}>
            {isEnglish ? 'Reset' : 'Zurücksetzen'}
          </button>
        </div>
        <table className="status-table">
          <caption className="sr-only">{isEnglish ? 'Audit events' : 'Audit-Events'}</caption>
          <thead>
            <tr>
              <th scope="col">{isEnglish ? 'Time' : 'Zeit'}</th>
              <th scope="col">{isEnglish ? 'Category' : 'Kategorie'}</th>
              <th scope="col">{isEnglish ? 'Action' : 'Aktion'}</th>
              <th scope="col">{isEnglish ? 'Object' : 'Objekt'}</th>
              <th scope="col">{isEnglish ? 'Description' : 'Beschreibung'}</th>
              <th scope="col">{isEnglish ? 'Actor' : 'Akteur'}</th>
              <th scope="col">{isEnglish ? 'Details' : 'Details'}</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id}>
                <td>{formatDate(entry.created_at)}</td>
                <td>
                  <span className={`pill ${entry.critical ? 'audit-pill-critical' : ''}`}>
                    {entry.category}
                  </span>
                </td>
                <td>{entry.action}</td>
                <td>
                  {entry.entity_type}
                  {entry.entity_id ? `:${entry.entity_id}` : ''}
                </td>
                <td>{entry.description || '–'}</td>
                <td>{entry.actor_name || 'system'}</td>
                <td>
                  <details>
                    <summary className="audit-summary">{isEnglish ? 'Show' : 'Anzeigen'}</summary>
                    <div className="audit-details-grid">
                      <div>
                        <div className="muted small">{isEnglish ? 'Before' : 'Vorher'}</div>
                        <pre className="audit-json">{prettyJson(entry.before)}</pre>
                      </div>
                      <div>
                        <div className="muted small">{isEnglish ? 'After' : 'Nachher'}</div>
                        <pre className="audit-json">{prettyJson(entry.after)}</pre>
                      </div>
                      <div>
                        <div className="muted small">Meta</div>
                        <pre className="audit-json">{prettyJson(entry.meta)}</pre>
                      </div>
                    </div>
                  </details>
                </td>
              </tr>
            ))}
            {entries.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
                  {isEnglish ? 'No audit events available.' : 'Keine Audit-Events vorhanden.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        <div className="row between mt8">
          <button
            className="btn"
            onClick={() => setOffset((current) => Math.max(0, current - limit))}
            disabled={offset <= 0}
          >
            {isEnglish ? '← Back' : '← Zurück'}
          </button>
          <span className="muted small">
            {isEnglish ? 'Offset' : 'Offset'} {offset} · {isEnglish ? 'Limit' : 'Limit'} {limit} ·{' '}
            {isEnglish ? 'Total' : 'Gesamt'} {total}
          </span>
          <button
            className="btn"
            onClick={() => setOffset((current) => current + limit)}
            disabled={entries.length < limit || offset + limit >= total}
          >
            {isEnglish ? 'Next →' : 'Weiter →'}
          </button>
        </div>
      </div>
    </div>
  )
}
