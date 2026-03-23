import React, { useEffect, useState } from 'react'
import { apiFetch } from '../../../api'
import { toDashboardProductVm, toDashboardTaskVm } from '../../../shared/api/mappers'
import type { DashboardProductVm, DashboardTaskVm } from '../../../shared/api/contracts'
import { parseContentTasksDtoArray, parseProductsDtoArray } from '../../../shared/api/validators'
import { getErrorMessage } from '../../../shared/lib/errors'
import { ErrorState } from '../../../shared/ui/states/ErrorState'
import { ListSkeleton } from '../../../shared/ui/states/ListSkeleton'

export default function DashboardPage() {
  const [products, setProducts] = useState<DashboardProductVm[]>([])
  const [tasks, setTasks] = useState<DashboardTaskVm[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  async function load() {
    try {
      setErr(null)
      setLoading(true)
      const p = parseProductsDtoArray(await apiFetch<unknown>('/products?limit=5&offset=0'))
      const t = parseContentTasksDtoArray(await apiFetch<unknown>('/content/tasks'))
      setProducts(p.map(toDashboardProductVm).filter(product => product.id >= 0))
      setTasks(t.map(toDashboardTaskVm).filter(task => task.id >= 0).slice(0, 5))
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const openTasks = tasks.filter(t => t.status !== 'done').length
  const inStock = products.filter(p => p.status === 'active').length
  const avgValue = products.length
    ? Math.round(
        products.reduce((sum, p) => sum + p.currentValue, 0) / products.length,
      )
    : 0

  const statusRows = products.slice(0, 5).map((product, index) => {
    const status = product.status === 'active' ? 'Lagernd' : product.status === 'sold' ? 'Verkauft' : 'Prüfung'
    return {
      id: product.id,
      name: product.title,
      icon: ['◼', '◆', '●', '▲', '■'][index % 5],
      amount: product.quantity,
      value: product.currentValue,
      status,
    }
  })

  const activityItems = [
    ...tasks.slice(0, 3).map((task, idx) => ({
      id: `task-${task.id}`,
      icon: idx % 2 ? '✎' : '✔',
      color: idx % 2 ? 'info' : 'success',
      title: task.title || 'Neue Aufgabe',
      time: task.updatedAt ? new Date(task.updatedAt).toLocaleString('de-DE') : 'Gerade eben',
    })),
    ...products.slice(0, 2).map(product => ({
      id: `product-${product.id}`,
      icon: '◫',
      color: 'warn',
      title: `${product.title} aktualisiert`,
      time: product.updatedAt ? new Date(product.updatedAt).toLocaleString('de-DE') : 'Heute',
    })),
  ].slice(0, 5)

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

      <section className="kpi-grid">
        <article className="kpi-card kpi-success">
          <div className="kpi-label">UMSATZ</div>
          <div className="kpi-value">€ {avgValue.toLocaleString('de-DE')}</div>
          <div className="kpi-trend">↑ 12,4%</div>
          <div className="kpi-watermark">€</div>
        </article>
        <article className="kpi-card kpi-violet">
          <div className="kpi-label">AUFGABEN</div>
          <div className="kpi-value">{openTasks}</div>
          <div className="kpi-trend">↑ 4,1%</div>
          <div className="kpi-watermark">✓</div>
        </article>
        <article className="kpi-card kpi-info">
          <div className="kpi-label">KUNDEN</div>
          <div className="kpi-value">{products.length}</div>
          <div className="kpi-trend">↑ 9,7%</div>
          <div className="kpi-watermark">◌</div>
        </article>
        <article className="kpi-card kpi-warn">
          <div className="kpi-label">BESTAND</div>
          <div className="kpi-value">{inStock}</div>
          <div className="kpi-trend">↓ 2,3%</div>
          <div className="kpi-watermark">◫</div>
        </article>
      </section>

      <section className="dashboard-mid-grid">
        <article className="card chart-card">
          <div className="card-head">
            <h3>Übersicht</h3>
            <button className="btn" type="button">Export</button>
          </div>
          <div className="line-chart-wrap">
            <svg viewBox="0 0 860 280" className="line-chart" role="img" aria-label="Monatsübersicht">
              <polygon
                points="20,240 100,210 180,220 260,180 340,170 420,150 500,165 580,120 660,130 740,95 820,85 820,240 20,240"
                fill="rgba(69,208,139,0.25)"
                stroke="none"
              />
              <polyline
                points="20,240 100,210 180,220 260,180 340,170 420,150 500,165 580,120 660,130 740,95 820,85"
                fill="none"
                stroke="#007bff"
                strokeWidth="4"
                strokeLinecap="round"
              />
            </svg>
            <div className="chart-months">
              {['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun', 'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez'].map(month => (
                <span key={month}>{month}</span>
              ))}
            </div>
          </div>
        </article>

        <article className="card donut-card">
          <div className="card-head">
            <h3>Quellen</h3>
          </div>
          <div className="donut-ring" />
          <div className="donut-legend">
            <span><i className="dot dot-blue" />Web</span>
            <span><i className="dot dot-violet" />Import</span>
            <span><i className="dot dot-green" />Direkt</span>
          </div>
        </article>
      </section>

      <section className="dashboard-bottom-grid">
        <article className="card activity-card">
          <div className="card-head">
            <h3>Aktivität</h3>
          </div>
          <div className="activity-list">
            {activityItems.map(item => (
              <div className="activity-item" key={item.id}>
                <div className={`activity-icon ${item.color}`}>{item.icon}</div>
                <div>
                  <div className="activity-title">{item.title}</div>
                  <div className="activity-time">{item.time}</div>
                </div>
              </div>
            ))}
            {activityItems.length === 0 && <div className="muted">Keine Aktivitäten.</div>}
          </div>
        </article>

        <article className="card status-card">
          <div className="card-head">
            <h3>Status</h3>
          </div>
          <table className="status-table">
            <thead>
              <tr>
                <th>Produkt</th>
                <th>Anzahl</th>
                <th>Wert</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {statusRows.map(row => (
                <tr key={row.id}>
                  <td>
                    <span className="product-with-icon">
                      <span className="product-icon">{row.icon}</span>
                      <span>{row.name}</span>
                    </span>
                  </td>
                  <td>{row.amount}</td>
                  <td>€ {row.value.toLocaleString('de-DE')}</td>
                  <td>
                    <span className={`status-badge ${row.status === 'Lagernd' ? 'ok' : row.status === 'Verkauft' ? 'danger' : 'warn'}`}>
                      {row.status}
                    </span>
                  </td>
                </tr>
              ))}
              {statusRows.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">Noch keine Produkte.</td>
                </tr>
              )}
            </tbody>
          </table>
        </article>
      </section>
        </>
      )}
    </div>
  )
}