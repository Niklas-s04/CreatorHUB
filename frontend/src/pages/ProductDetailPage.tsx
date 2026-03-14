import React, { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { apiFetch, apiFetchBlob } from '../api'

function useThumb(assetId: string | null) {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    let active = true
    let obj: string | null = null
    ;(async () => {
      if (!assetId) { setUrl(null); return }
      try {
        const blob = await apiFetchBlob(`/assets/${assetId}/thumb`)
        obj = URL.createObjectURL(blob)
        if (active) setUrl(obj)
      } catch {
        if (active) setUrl(null)
      }
    })()
    return () => {
      active = false
      if (obj) URL.revokeObjectURL(obj)
    }
  }, [assetId])
  return url
}

function stripHtml(s: string) {
  return s.replace(/<[^>]*>/g, '').trim()
}

export default function ProductDetailPage() {
  const { id } = useParams()
  const [product, setProduct] = useState<any>(null)
  const [assets, setAssets] = useState<any[]>([])
  const [txs, setTxs] = useState<any[]>([])
  const [err, setErr] = useState<string | null>(null)

  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)

  const [status, setStatus] = useState('active')
  const [txDate, setTxDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [amount, setAmount] = useState<string>('')

  const [imageQuery, setImageQuery] = useState('')
  const [imageSource, setImageSource] = useState('auto')
  const [jobId, setJobId] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<string | null>(null)
  const [jobResult, setJobResult] = useState<any>(null)

  async function load() {
    if (!id) return
    try {
      setErr(null)
      const p = await apiFetch(`/products/${id}`)
      const a = await apiFetch(`/assets?owner_type=product&owner_id=${id}&include_pending=true`)
      const t = await apiFetch(`/products/${id}/transactions`)
      setProduct(p)
      setAssets(a)
      setTxs(t)
      setNotes(p.notes_md || '')
      setStatus(p.status)
      if (!imageQuery) {
        const q = [p.brand, p.model, p.title].filter(Boolean).join(' ')
        setImageQuery(q)
      }
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  useEffect(() => { load() }, [id])

  const primary = useMemo(() => {
    const approved = assets.filter(a => a.review_state === 'approved')
    return approved.find(a => a.is_primary) || approved[0] || null
  }, [assets])

  const primaryThumb = useThumb(primary?.id || null)

  async function saveNotes() {
    if (!id) return
    setSaving(true)
    try {
      await apiFetch(`/products/${id}`, { method: 'PATCH', body: JSON.stringify({ notes_md: notes }) })
      await load()
    } catch (e: any) {
      setErr(e.message || String(e))
    } finally {
      setSaving(false)
    }
  }

  async function changeStatus() {
    if (!id) return
    try {
      setErr(null)
      await apiFetch(`/products/${id}/status`, {
        method: 'POST',
        body: JSON.stringify({
          status,
          tx_date: txDate,
          amount: amount ? parseFloat(amount) : null
        })
      })
      setAmount('')
      await load()
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  async function upload(file: File) {
    if (!id) return
    try {
      setErr(null)
      const form = new FormData()
      form.append('file', file)
      form.append('owner_type', 'product')
      form.append('owner_id', id)
      await fetch('/api/assets/upload', { method: 'POST', body: form, credentials: 'include' })
      await load()
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  async function startImageHunt() {
    if (!id) return
    try {
      setErr(null)
      setJobResult(null)
      setJobStatus('queued')
      const r = await apiFetch('/images/search', {
        method: 'POST',
        body: JSON.stringify({ product_id: id, query: imageQuery, max_results: 12, source: imageSource })
      })
      setJobId(String(r.job_id))
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  async function pollJob() {
    if (!jobId) return
    try {
      const r = await apiFetch(`/images/jobs/${jobId}`)
      setJobStatus(r.status)
      if (r.status === 'finished') {
        setJobResult(r.result)
        await load()
      }
      if (r.status === 'failed') {
        setErr(r.error || 'Job failed')
      }
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  useEffect(() => {
    if (!jobId) return
    let timer: any = null
    const tick = async () => {
      await pollJob()
      timer = setTimeout(tick, 1200)
    }
    tick()
    return () => { if (timer) clearTimeout(timer) }
  }, [jobId])

  async function review(assetId: number, state: 'approved' | 'rejected') {
    await apiFetch(`/assets/${assetId}`, { method: 'PATCH', body: JSON.stringify({ review_state: state }) })
    await load()
  }

  async function setPrimary(assetId: number) {
    await apiFetch(`/assets/${assetId}/primary`, { method: 'POST' })
    await load()
  }

  if (!product) {
    return (
      <div className="container">
        <h2>Produkt</h2>
        {err && <div className="error">{err}</div>}
        <div className="muted">Lädt…</div>
      </div>
    )
  }

  return (
    <div className="container">
      <div className="row between">
        <h2>Produkt</h2>
        <span className="muted small">ID {product.id}</span>
      </div>

      {err && <div className="error">{err}</div>}

      <div className="row" style={{ alignItems: 'stretch' }}>
        <div className="card grow" style={{ minWidth: 320 }}>
          <div className="row between">
            <div>
              <div style={{ fontWeight: 900, fontSize: 18 }}>{product.title}</div>
              <div className="muted small">
                {[product.brand, product.model].filter(Boolean).join(' • ') || '—'}
              </div>
            </div>
            <div className="row">
              <span className="pill">{product.status}</span>
              <span className="pill">{product.condition}</span>
            </div>
          </div>

          <hr />

          <div className="row">
            <div className="grow">
              <div className="muted small" style={{ marginBottom: 6 }}>Status</div>
              <select className="w100" value={status} onChange={e => setStatus(e.target.value)}>
                <option value="active">active</option>
                <option value="sold">sold</option>
                <option value="gifted">gifted</option>
                <option value="returned">returned</option>
                <option value="broken">broken</option>
                <option value="archived">archived</option>
              </select>
            </div>
            <div>
              <div className="muted small" style={{ marginBottom: 6 }}>Datum</div>
              <input type="date" value={txDate} onChange={e => setTxDate(e.target.value)} />
            </div>
            <div>
              <div className="muted small" style={{ marginBottom: 6 }}>Betrag</div>
              <input placeholder="z.B. 120" value={amount} onChange={e => setAmount(e.target.value)} />
            </div>
            <button className="btn primary" onClick={changeStatus}>Apply</button>
          </div>

          <hr />

          <div className="muted small" style={{ marginBottom: 6 }}>Notes</div>
          <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={8} />
          <div className="row mt12">
            <button className="btn primary" onClick={saveNotes} disabled={saving}>
              {saving ? '...' : 'Speichern'}
            </button>
          </div>
        </div>

        <div className="card" style={{ width: 420 }}>
          <div className="row between">
            <h3>Bild</h3>
            <span className="muted small">{primary ? 'primary' : '—'}</span>
          </div>

          {primaryThumb ? (
            <img src={primaryThumb} className="img" />
          ) : (
            <div className="muted">Kein Preview.</div>
          )}

          <hr />

          <div className="muted small" style={{ marginBottom: 6 }}>Upload</div>
          <input type="file" onChange={e => {
            const f = e.target.files?.[0]
            if (f) upload(f)
          }} />

          <hr />

          <div className="muted small" style={{ marginBottom: 6 }}>Web-Bild (Quelle)</div>
          <div className="row">
            <input className="grow" value={imageQuery} onChange={e => setImageQuery(e.target.value)} placeholder="Query…" />
            <select value={imageSource} onChange={e => setImageSource(e.target.value)}>
              <option value="auto">auto</option>
              <option value="wikimedia">wikimedia</option>
              <option value="bing">bing</option>
              <option value="manufacturer">manufacturer</option>
              <option value="wikimedia,bing">wikimedia,bing</option>
            </select>
            <button className="btn" onClick={startImageHunt}>Search</button>
          </div>
          {jobStatus && <div className="muted small mt12">Job: {jobStatus}</div>}
        </div>
      </div>

      <div className="card mt16">
        <div className="row between">
          <h3>Assets</h3>
          <span className="muted small">approve → primary</span>
        </div>

        <div className="grid mt12">
          {assets.map(a => (
            <AssetCard
              key={a.id}
              asset={a}
              onReview={review}
              onPrimary={setPrimary}
            />
          ))}
          {!assets.length && <div className="muted">Keine Assets.</div>}
        </div>

        {jobResult?.candidates?.length ? (
          <>
            <hr />
            <div className="muted small">Letzte Search: {jobResult.query} • {jobResult.count}</div>
          </>
        ) : null}
      </div>

      <div className="card mt16">
        <div className="row between">
          <h3>Transaktionen</h3>
          <span className="muted small">{txs.length}</span>
        </div>

        <table>
          <thead>
            <tr>
              <th>Typ</th>
              <th>Datum</th>
              <th>Betrag</th>
              <th>Notiz</th>
            </tr>
          </thead>
          <tbody>
            {txs.map(t => (
              <tr key={t.id}>
                <td><span className="pill">{t.tx_type}</span></td>
                <td>{t.tx_date}</td>
                <td>{t.amount ?? ''} {t.currency ?? ''}</td>
                <td className="muted small">{t.note ?? ''}</td>
              </tr>
            ))}
            {!txs.length && (
              <tr>
                <td colSpan={4} className="muted">Keine Transaktionen.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function AssetCard({
  asset,
  onReview,
  onPrimary
}: {
  asset: any
  onReview: (id: number, state: 'approved' | 'rejected') => void
  onPrimary: (id: number) => void
}) {
  const thumb = useThumb(String(asset.id))
  return (
    <div className={asset.review_state === 'pending' ? 'card tight' : 'card tight'}>
      {thumb ? <img src={thumb} className="img" /> : <div className="muted">No preview</div>}

      <div style={{ marginTop: 8, fontWeight: 900, fontSize: 13 }}>
        {asset.title || `asset ${asset.id}`}
      </div>

      <div className="muted small">
        {asset.source} • {asset.review_state} {asset.is_primary ? '• primary' : ''}
      </div>

      {(asset.license_type || asset.attribution) && (
        <div className="muted small" style={{ marginTop: 6 }}>
          {asset.license_type ? `Lizenz: ${asset.license_type}` : ''}
          {asset.license_type && asset.attribution ? ' • ' : ''}
          {asset.attribution ? `Attribution: ${stripHtml(asset.attribution)}` : ''}
        </div>
      )}

      {(asset.source_url || asset.license_url) && (
        <div className="muted small" style={{ marginTop: 6 }}>
          {asset.source_url ? <a href={asset.source_url} target="_blank" rel="noreferrer">Quelle</a> : null}
          {asset.source_url && asset.license_url ? ' • ' : null}
          {asset.license_url ? <a href={asset.license_url} target="_blank" rel="noreferrer">Lizenz</a> : null}
        </div>
      )}

      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn" onClick={() => onPrimary(asset.id)}>Primary</button>
        {asset.review_state !== 'approved' && (
          <button className="btn primary" onClick={() => onReview(asset.id, 'approved')}>Approve</button>
        )}
        {asset.review_state !== 'rejected' && (
          <button className="btn danger" onClick={() => onReview(asset.id, 'rejected')}>Reject</button>
        )}
      </div>
    </div>
  )
}