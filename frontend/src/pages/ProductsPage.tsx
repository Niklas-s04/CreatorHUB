import React, { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { Link } from 'react-router-dom'

export default function ProductsPage() {
  const [items, setItems] = useState<any[]>([])
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newBrand, setNewBrand] = useState('')
  const [newModel, setNewModel] = useState('')
  const [newValue, setNewValue] = useState<string>('')
  const [exportDataset, setExportDataset] = useState<'products' | 'transactions' | 'value_history'>('products')
  const [exportYears, setExportYears] = useState('')

  async function load() {
    try {
      setErr(null)
      const params = new URLSearchParams()
      params.set('limit', '100')
      if (q) params.set('q', q)
      if (status) params.set('status', status)

      const data = await apiFetch(`/products?${params.toString()}`)
      setItems(data)
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  useEffect(() => { load() }, [])

  async function create() {
    try {
      setErr(null)
      const payload: any = { title: newTitle }
      if (newBrand) payload.brand = newBrand
      if (newModel) payload.model = newModel
      if (newValue) payload.current_value = parseFloat(newValue)
      await apiFetch('/products', { method: 'POST', body: JSON.stringify(payload) })
      setShowNew(false)
      setNewTitle(''); setNewBrand(''); setNewModel(''); setNewValue('')
      await load()
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  function handleExport() {
    const params = new URLSearchParams()
    params.set('dataset', exportDataset)
    const yearTokens = exportYears
      .split(/[,\s]+/)
      .map(token => token.trim())
      .filter(Boolean)
    yearTokens.forEach(year => {
      const parsed = parseInt(year, 10)
      if (!Number.isNaN(parsed)) {
        params.append('years', String(parsed))
      }
    })
    const qs = params.toString()
    const url = `/api/products/export/csv${qs ? `?${qs}` : ''}`
    window.open(url, '_blank', 'noreferrer')
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h2 className="page-title">Inventar</h2>
          <div className="page-subtitle">Produkte verwalten, filtern und exportieren.</div>
        </div>
        <div className="page-actions">
          <button className="btn primary" onClick={() => setShowNew(v => !v)}>
            {showNew ? 'Schließen' : '+ Produkt'}
          </button>
          <div className="control-row">
            <select value={exportDataset} onChange={e => setExportDataset(e.target.value as typeof exportDataset)}>
              <option value="products">Produkte</option>
              <option value="transactions">Transaktionen</option>
              <option value="value_history">Wert-Historie</option>
            </select>
            <input
              className="w180"
              placeholder="Jahre z.B. 2023,2024"
              value={exportYears}
              onChange={e => setExportYears(e.target.value)}
            />
            <button className="btn" onClick={handleExport}>
              Export CSV
            </button>
          </div>
        </div>
      </div>

      {err && <div className="error">{err}</div>}

      {showNew && (
        <div className="card section-gap">
          <div className="page-header no-margin">
            <h3>Neues Produkt</h3>
            <button className="btn" onClick={create} disabled={!newTitle.trim()}>Speichern</button>
          </div>

          <div className="control-row section-gap">
            <input className="grow" placeholder="Titel*" value={newTitle} onChange={e => setNewTitle(e.target.value)} />
            <input placeholder="Brand" value={newBrand} onChange={e => setNewBrand(e.target.value)} />
            <input placeholder="Model" value={newModel} onChange={e => setNewModel(e.target.value)} />
            <input placeholder="Wert (EUR)" value={newValue} onChange={e => setNewValue(e.target.value)} />
          </div>
        </div>
      )}

      <div className="card section-gap">
        <div className="page-header mb10">
          <div className="control-row flex1">
            <input className="grow" placeholder="Suche…" value={q} onChange={e => setQ(e.target.value)} />
            <select value={status} onChange={e => setStatus(e.target.value)}>
              <option value="">Status: alle</option>
              <option value="active">active</option>
              <option value="sold">sold</option>
              <option value="gifted">gifted</option>
              <option value="returned">returned</option>
              <option value="broken">broken</option>
              <option value="archived">archived</option>
            </select>
            <button className="btn" onClick={load}>Filter</button>
          </div>
          <span className="muted small">{items.length} items</span>
        </div>

        <table>
          <thead>
            <tr>
              <th>Titel</th>
              <th>Kategorie</th>
              <th>Zustand</th>
              <th>Status</th>
              <th>Wert</th>
            </tr>
          </thead>
          <tbody>
            {items.map(p => (
              <tr key={p.id}>
                <td><Link to={`/products/${p.id}`}>{p.title}</Link></td>
                <td>{p.category ?? ''}</td>
                <td><span className="pill">{p.condition}</span></td>
                <td><span className="pill">{p.status}</span></td>
                <td>{p.current_value ?? ''} {p.currency ?? ''}</td>
              </tr>
            ))}
            {!items.length && (
              <tr>
                <td colSpan={5} className="muted">Keine Treffer.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}