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
        created_at: typeof item.created_at === 'string' ? item.created_at : '',
      }
    })
    .filter((entry): entry is AuditEntry => Boolean(entry && entry.id))
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
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState<string | null>(null)

  async function load() {
    if (!canViewAudit) {
      setEntries([])
      setLoading(false)
      return
    }

    try {
      setErr(null)
      setLoading(true)
      const response = await apiFetch<PageLike<AuditEntry>>('/audit?limit=50&offset=0&sort_by=created_at&sort_order=desc')
      setEntries(parseAuditEntries(response))
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (authzLoading) return
    void load()
  }, [authzLoading, canViewAudit])

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
          <button className="btn" onClick={() => {
            void load()
          }}>
            Refresh
          </button>
        </div>
        <table className="status-table">
          <thead>
            <tr>
              <th>Zeit</th>
              <th>Aktion</th>
              <th>Objekt</th>
              <th>Beschreibung</th>
              <th>Akteur</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(entry => (
              <tr key={entry.id}>
                <td>{formatDate(entry.created_at)}</td>
                <td>{entry.action}</td>
                <td>{entry.entity_type}{entry.entity_id ? `:${entry.entity_id}` : ''}</td>
                <td>{entry.description || '–'}</td>
                <td>{entry.actor_name || 'system'}</td>
              </tr>
            ))}
            {entries.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">Keine Audit-Events vorhanden.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
