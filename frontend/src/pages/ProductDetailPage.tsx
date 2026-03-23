import React, { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { apiFetch, apiFetchBlob } from '../api'
import { useAuthz } from '../hooks/useAuthz'

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
  const { hasPermission } = useAuthz()
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
  const canWriteProduct = hasPermission('product.write')
  const canUploadAsset = hasPermission('asset.upload')
  const canReviewAsset = hasPermission('asset.review')
  const canSearchImages = hasPermission('image.search')

  async function saveNotes() {
    if (!hasPermission('product.write')) return
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
    if (!hasPermission('product.write')) return
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
    if (!hasPermission('asset.upload')) return
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
    if (!hasPermission('image.search')) return
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
    if (!hasPermission('asset.review')) return
    await apiFetch(`/assets/${assetId}`, { method: 'PATCH', body: JSON.stringify({ review_state: state }) })
    await load()
  }

  async function setPrimary(assetId: number) {
    if (!hasPermission('asset.review')) return
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
      <div className="page-header">
        <div>
          <h2 className="page-title">Produkt</h2>
          <div className="page-subtitle">Detailansicht und Asset-/Statusverwaltung.</div>
        </div>
        <span className="muted small">ID {product.id}</span>
      </div>

      {err && <div className="error">{err}</div>}

      <div className="product-layout">
        <div className="card product-main">
          <div className="row between">
            <div>
              <div className="title-strong">{product.title}</div>
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
              <div className="field-label">Status</div>
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
              <div className="field-label">Datum</div>
              <input type="date" value={txDate} onChange={e => setTxDate(e.target.value)} />
            </div>
            <div>
              <div className="field-label">Betrag</div>
              <input placeholder="z.B. 120" value={amount} onChange={e => setAmount(e.target.value)} />
            </div>
            <button className="btn primary" onClick={changeStatus} disabled={!canWriteProduct}>Apply</button>
          </div>

          <hr />

          <div className="field-label">Notes</div>
          <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={8} />
          <div className="row mt12">
            <button className="btn primary" onClick={saveNotes} disabled={!canWriteProduct || saving}>
              {saving ? '...' : 'Speichern'}
            </button>
          </div>
        </div>

        <div className="card product-side">
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

          <div className="field-label">Upload</div>
          <input type="file" disabled={!canUploadAsset} onChange={e => {
            const f = e.target.files?.[0]
            if (f) upload(f)
          }} />

          <hr />

          <div className="field-label">Web-Bild (Quelle)</div>
          <div className="row">
            <input className="grow" value={imageQuery} onChange={e => setImageQuery(e.target.value)} placeholder="Query…" />
            <select value={imageSource} onChange={e => setImageSource(e.target.value)}>
              <option value="auto">auto</option>
              <option value="wikimedia">wikimedia</option>
              <option value="bing">bing</option>
              <option value="manufacturer">manufacturer</option>
              <option value="wikimedia,bing">wikimedia,bing</option>
            </select>
            <button className="btn" onClick={startImageHunt} disabled={!canSearchImages}>Search</button>
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
              canReview={canReviewAsset}
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
  onPrimary,
  canReview
}: {
  asset: any
  onReview: (id: number, state: 'approved' | 'rejected') => void
  onPrimary: (id: number) => void
  canReview: boolean
}) {
  const thumb = useThumb(String(asset.id))
  return (
    <div className={asset.review_state === 'pending' ? 'card tight' : 'card tight'}>
      {thumb ? <img src={thumb} className="img" /> : <div className="muted">No preview</div>}

      <div className="asset-title">
        {asset.title || `asset ${asset.id}`}
      </div>

      <div className="muted small">
        {asset.source} • {asset.review_state} {asset.is_primary ? '• primary' : ''}
      </div>

      {(asset.license_type || asset.attribution) && (
        <div className="muted small mt6">
          {asset.license_type ? `Lizenz: ${asset.license_type}` : ''}
          {asset.license_type && asset.attribution ? ' • ' : ''}
          {asset.attribution ? `Attribution: ${stripHtml(asset.attribution)}` : ''}
        </div>
      )}

      {(asset.source_url || asset.license_url) && (
        <div className="muted small mt6">
          {asset.source_url ? <a href={asset.source_url} target="_blank" rel="noreferrer">Quelle</a> : null}
          {asset.source_url && asset.license_url ? ' • ' : null}
          {asset.license_url ? <a href={asset.license_url} target="_blank" rel="noreferrer">Lizenz</a> : null}
        </div>
      )}

      <div className="row mt10">
        <button className="btn" onClick={() => onPrimary(asset.id)} disabled={!canReview}>Primary</button>
        {canReview && asset.review_state !== 'approved' && (
          <button className="btn primary" onClick={() => onReview(asset.id, 'approved')}>Approve</button>
        )}
        {canReview && asset.review_state !== 'rejected' && (
          <button className="btn danger" onClick={() => onReview(asset.id, 'rejected')}>Reject</button>
        )}
      </div>
    </div>
  )
}