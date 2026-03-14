import React, { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { Link } from 'react-router-dom'

export default function DashboardPage() {
  const [products, setProducts] = useState<any[]>([])
  const [tasks, setTasks] = useState<any[]>([])
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    ;(async () => {
      try {
        const p = await apiFetch('/products?limit=5&offset=0')
        const t = await apiFetch('/content/tasks')
        setProducts(p)
        setTasks(t.slice(0, 5))
      } catch (e: any) {
        setErr(e.message || String(e))
      }
    })()
  }, [])

  const openTasks = tasks.filter(t => t.status !== 'done').length

  return (
    <div className="container">
      <div className="row between">
        <h2>Dashboard</h2>
        <div className="row">
          <Link to="/products" className="btn primary">+ Produkt</Link>
          <Link to="/email" className="btn">E-Mail</Link>
        </div>
      </div>

      {err && <div className="error">{err}</div>}

      <div className="row">
        <div className="card grow" style={{ minWidth: 240 }}>
          <div className="muted">Aktive Produkte</div>
          <div className="kpi">{products.length}</div>
          <div className="muted small">Quick View (Limit 5)</div>
        </div>

        <div className="card grow" style={{ minWidth: 240 }}>
          <div className="muted">Offene Tasks</div>
          <div className="kpi">{openTasks}</div>
          <div className="muted small">Content → Tasks</div>
        </div>
      </div>

      <div className="card mt16">
        <div className="row between">
          <h3>Zuletzt geändert</h3>
          <span className="muted small">Produkte</span>
        </div>
        <table>
          <thead>
            <tr>
              <th>Titel</th>
              <th>Status</th>
              <th>Wert</th>
            </tr>
          </thead>
          <tbody>
            {products.map(p => (
              <tr key={p.id}>
                <td><Link to={`/products/${p.id}`}>{p.title}</Link></td>
                <td><span className="pill">{p.status}</span></td>
                <td>{p.current_value ?? ''} {p.currency ?? ''}</td>
              </tr>
            ))}
            {!products.length && (
              <tr>
                <td colSpan={3} className="muted">Noch keine Produkte.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}