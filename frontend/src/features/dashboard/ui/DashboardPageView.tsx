import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../../api'
import { getErrorMessage } from '../../../shared/lib/errors'
import { ErrorState } from '../../../shared/ui/states/ErrorState'
import { ListSkeleton } from '../../../shared/ui/states/ListSkeleton'

type DashboardMetricKey =
  | 'open_deals'
  | 'unreviewed_assets'
  | 'overdue_tasks'
  | 'risky_email_drafts'
  | 'pending_registration_requests'
  | 'audit_incidents'

type DashboardTone = 'info' | 'warn' | 'danger'

type DashboardListItem = {
  id: string
  title: string
  subtitle: string | null
  updated_at: string | null
}

type DashboardMetric = {
  key: DashboardMetricKey
  label: string
  description: string
  count: number
  route: string
  tone: DashboardTone
  items: DashboardListItem[]
}

type DashboardSummary = {
  generated_at: string
  role: 'admin' | 'editor' | 'viewer' | string
  metrics: DashboardMetric[]
}

const ROLE_LABELS: Record<string, string> = {
  admin: 'Admin-Fokus: Governance, Freigaben und Security',
  editor: 'Editor-Fokus: Delivery, offene Freigaben und Risiken',
  viewer: 'Viewer-Fokus: Transparenz über operative Blocker',
}

const TONE_CLASS: Record<DashboardTone, string> = {
  info: 'kpi-info',
  warn: 'kpi-warn',
  danger: 'kpi-danger',
}

function formatTime(value: string | null): string {
  if (!value) return ''
  try {
    return new Date(value).toLocaleString('de-DE')
  } catch {
    return value
  }
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      setErr(null)
      setLoading(true)
      const data = await apiFetch<DashboardSummary>('/dashboard/summary')
      setSummary(data)
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const metrics = summary?.metrics ?? []
  const roleHint = useMemo(() => {
    if (!summary) return ''
    return ROLE_LABELS[summary.role] || `Rollenfokus: ${summary.role}`
  }, [summary])

  return (
    <div className="dashboard-layout">
      {loading && <ListSkeleton rows={6} />}
      {!loading && err && (
        <ErrorState
          title="Dashboard konnte nicht geladen werden"
          message={err}
          onRetry={() => {
            void load()
          }}
        />
      )}

      {!loading && !err && (
        <>
          <section className="card dashboard-role-card">
            <div className="card-head">
              <h3>Operatives Dashboard</h3>
            </div>
            <div className="muted">{roleHint}</div>
          </section>

          <section className="kpi-grid">
            {metrics.map(metric => (
              <Link
                to={metric.route}
                key={metric.key}
                className={`kpi-card kpi-link ${TONE_CLASS[metric.tone]}`}
                aria-label={`${metric.label}: ${metric.count}. Zur Arbeitsliste`}
              >
                <div className="kpi-label">{metric.label}</div>
                <div className="kpi-value">{metric.count}</div>
                <div className="kpi-trend">{metric.description}</div>
                <div className="kpi-drilldown">Zur Arbeitsliste →</div>
              </Link>
            ))}
            {metrics.length === 0 && (
              <article className="card">
                <h3>Keine operativen KPIs verfügbar</h3>
                <div className="muted">Für deine Rolle stehen aktuell keine Dashboard-Kennzahlen zur Verfügung.</div>
              </article>
            )}
          </section>

          <section className="dashboard-worklist-grid">
            {metrics.map(metric => (
              <article className="card" key={`${metric.key}-list`}>
                <div className="card-head">
                  <h3>{metric.label}</h3>
                  <Link className="btn" to={metric.route}>Öffnen</Link>
                </div>
                <div className="worklist-items">
                  {metric.items.map(item => (
                    <div key={item.id} className="worklist-item">
                      <div className="worklist-title">{item.title}</div>
                      {item.subtitle && <div className="worklist-subtitle">{item.subtitle}</div>}
                      {item.updated_at && <div className="worklist-time">{formatTime(item.updated_at)}</div>}
                    </div>
                  ))}
                  {metric.items.length === 0 && <div className="muted">Keine offenen Einträge.</div>}
                </div>
              </article>
            ))}
          </section>
        </>
      )}
    </div>
  )
}