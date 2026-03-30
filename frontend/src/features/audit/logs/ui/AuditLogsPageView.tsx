import { useEffect, useState } from 'react'
import { apiFetch } from '../../../../api'
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
    .map(item => {
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

  function buildQuery() {
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
    return params.toString()
  }

  async function load() {
    if (!canViewAudit) {
      setEntries([])
      setLoading(false)
      return
    }

    try {
      setErr(null)
      setLoading(true)
      const response = await apiFetch<PageLike<AuditEntry> & { meta?: { total?: number } }>(
        `/audit?${buildQuery()}`
      )
      const parsed = parseAuditEntries(response)
      setEntries(parsed)
      setTotal(typeof response.meta?.total === 'number' ? response.meta.total : parsed.length)
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (authzLoading) return
    void load()
  }, [
    authzLoading,
    canViewAudit,
    limit,
    offset,
    actionFilter,
    entityTypeFilter,
    actorFilter,
    searchFilter,
    categoryFilter,
    criticalOnly,
  ])

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
    const url = `/api/audit/export/csv${query ? `?${query}` : ''}`
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  if (authzLoading || loading) {
    return <ListSkeleton rows={8} />
  }

  if (!canViewAudit) {
    return (
      <div className="card">
        <h2>Audit</h2>
        <div className="muted">Keine Berechtigung für Audit-Logs.</div>
      </div>
    )
  }

  if (err) {
    return (
      <ErrorState
        title="Audit-Logs konnten nicht geladen werden"
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
          <h2>Audit-Logs</h2>
          <div className="control-row">
            <select value={String(limit)} onChange={event => {
              setLimit(Number(event.target.value))
              setOffset(0)
            }}>
              <option value="25">25 / Seite</option>
              <option value="50">50 / Seite</option>
            </select>
            <button className="btn" onClick={() => {
              void load()
            }}>
              Refresh
            </button>
            <button className="btn" onClick={handleExportCsv}>
              Export CSV
            </button>
          </div>
        </div>
        <div className="audit-filters" role="region" aria-label="Audit Filter">
          <input
            value={actionFilter}
            onChange={event => {
              setActionFilter(event.target.value)
              setOffset(0)
            }}
            placeholder="Aktion"
            aria-label="Filter Aktion"
          />
          <input
            value={entityTypeFilter}
            onChange={event => {
              setEntityTypeFilter(event.target.value)
              setOffset(0)
            }}
            placeholder="Objekttyp"
            aria-label="Filter Objekttyp"
          />
          <input
            value={actorFilter}
            onChange={event => {
              setActorFilter(event.target.value)
              setOffset(0)
            }}
            placeholder="Akteur"
            aria-label="Filter Akteur"
          />
          <input
            value={searchFilter}
            onChange={event => {
              setSearchFilter(event.target.value)
              setOffset(0)
            }}
            placeholder="Suche"
            aria-label="Audit Suche"
          />
          <select
            value={categoryFilter}
            onChange={event => {
              setCategoryFilter(event.target.value)
              setOffset(0)
            }}
            aria-label="Filter Kategorie"
          >
            <option value="">Alle Kategorien</option>
            <option value="approval">Freigaben</option>
            <option value="permission_change">Rechteänderungen</option>
            <option value="security">Security</option>
            <option value="ai_action">AI-Aktionen</option>
            <option value="domain">Domain</option>
          </select>
          <label className="audit-checkbox">
            <input
              type="checkbox"
              checked={criticalOnly}
              onChange={event => {
                setCriticalOnly(event.target.checked)
                setOffset(0)
              }}
            />
            Nur kritisch
          </label>
          <button className="btn" onClick={resetFilters}>Zurücksetzen</button>
        </div>
        <table className="status-table">
          <caption className="sr-only">Audit-Events</caption>
          <thead>
            <tr>
              <th scope="col">Zeit</th>
              <th scope="col">Kategorie</th>
              <th scope="col">Aktion</th>
              <th scope="col">Objekt</th>
              <th scope="col">Beschreibung</th>
              <th scope="col">Akteur</th>
              <th scope="col">Details</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(entry => (
              <tr key={entry.id}>
                <td>{formatDate(entry.created_at)}</td>
                <td>
                  <span className={`pill ${entry.critical ? 'audit-pill-critical' : ''}`}>
                    {entry.category}
                  </span>
                </td>
                <td>{entry.action}</td>
                <td>{entry.entity_type}{entry.entity_id ? `:${entry.entity_id}` : ''}</td>
                <td>{entry.description || '–'}</td>
                <td>{entry.actor_name || 'system'}</td>
                <td>
                  <details>
                    <summary className="audit-summary">Anzeigen</summary>
                    <div className="audit-details-grid">
                      <div>
                        <div className="muted small">Vorher</div>
                        <pre className="audit-json">{prettyJson(entry.before)}</pre>
                      </div>
                      <div>
                        <div className="muted small">Nachher</div>
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
                <td colSpan={7} className="muted">Keine Audit-Events vorhanden.</td>
              </tr>
            )}
          </tbody>
        </table>
        <div className="row between mt8">
          <button className="btn" onClick={() => setOffset(current => Math.max(0, current - limit))} disabled={offset <= 0}>← Zurück</button>
          <span className="muted small">Offset {offset} · Limit {limit} · Gesamt {total}</span>
          <button className="btn" onClick={() => setOffset(current => current + limit)} disabled={entries.length < limit || offset + limit >= total}>Weiter →</button>
        </div>
      </div>
    </div>
  )
}
