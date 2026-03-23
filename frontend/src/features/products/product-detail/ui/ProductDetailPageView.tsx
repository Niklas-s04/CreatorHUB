import React, { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { apiFetch } from '../../../../api'
import { PRODUCT_STATUS_OPTIONS } from '../../../../entities/product/model'
import type {
  ImageSearchJobDto,
} from '../../../../shared/api/contracts'
import {
  parseImageSearchJobDto,
} from '../../../../shared/api/validators'
import {
  useChangeProductStatusMutation,
  useProductAssetsQuery,
  useProductDetailQuery,
  useProductTransactionsQuery,
  useReviewAssetMutation,
  useSetPrimaryAssetMutation,
  useUpdateProductNotesMutation,
} from '../../../../shared/api/queries/products'
import { useAuthz } from '../../../../shared/hooks/useAuthz'
import { getErrorMessage } from '../../../../shared/lib/errors'
import { AssetCard } from './AssetCard'
import { useThumb } from './useThumb'

export default function ProductDetailPageView() {
  const { hasPermission } = useAuthz()
  const { id } = useParams()
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
  const [jobResult, setJobResult] = useState<ImageSearchJobDto['result']>(null)
  const productQuery = useProductDetailQuery(id)
  const assetsQuery = useProductAssetsQuery(id)
  const transactionsQuery = useProductTransactionsQuery(id)

  const product = productQuery.data ?? null
  const assets = assetsQuery.data ?? []
  const txs = transactionsQuery.data ?? []

  const updateNotesMutation = useUpdateProductNotesMutation()
  const changeStatusMutation = useChangeProductStatusMutation()
  const reviewMutation = useReviewAssetMutation(id)
  const setPrimaryMutation = useSetPrimaryAssetMutation(id)

  useEffect(() => {
    if (!product) return
    setNotes(product.notes)
    setStatus(product.status)
    if (!imageQuery) {
      const q = [product.brand, product.model, product.title].filter(Boolean).join(' ')
      setImageQuery(q)
    }
  }, [product])

  const primary = useMemo(() => {
    const approved = assets.filter(a => a.reviewState === 'approved')
    return approved.find(a => a.isPrimary) || approved[0] || null
  }, [assets])

  const primaryThumb = useThumb(primary ? String(primary.id) : null)
  const canWriteProduct = hasPermission('product.write')
  const canUploadAsset = hasPermission('asset.upload')
  const canReviewAsset = hasPermission('asset.review')
  const canSearchImages = hasPermission('image.search')

  async function saveNotes() {
    if (!hasPermission('product.write')) return
    if (!id) return
    setSaving(true)
    try {
      await updateNotesMutation.mutateAsync({ id, notes_md: notes })
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  async function changeStatus() {
    if (!hasPermission('product.write')) return
    if (!id) return
    try {
      setErr(null)
      await changeStatusMutation.mutateAsync({
        id,
        status,
        tx_date: txDate,
        amount: amount ? parseFloat(amount) : null,
      })
      setAmount('')
      await Promise.all([
        productQuery.refetch(),
        transactionsQuery.refetch(),
      ])
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
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
      await assetsQuery.refetch()
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    }
  }

  async function startImageHunt() {
    if (!hasPermission('image.search')) return
    if (!id) return
    try {
      setErr(null)
      setJobResult(null)
      setJobStatus('queued')
      const r = await apiFetch<{ job_id?: string | number }>('/images/search', {
        method: 'POST',
        body: JSON.stringify({ product_id: id, query: imageQuery, max_results: 12, source: imageSource })
      })
      if (typeof r.job_id === 'string' || typeof r.job_id === 'number') {
        setJobId(String(r.job_id))
      } else {
        setErr('Ungültige Job-Antwort vom Server')
      }
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    }
  }

  async function pollJob() {
    if (!jobId) return
    try {
      const r = parseImageSearchJobDto(await apiFetch<unknown>(`/images/jobs/${jobId}`))
      setJobStatus(r.status)
      if (r.status === 'finished') {
        setJobResult(r.result)
        await Promise.all([
          assetsQuery.refetch(),
          productQuery.refetch(),
        ])
      }
      if (r.status === 'failed') {
        setErr(r.error || 'Job failed')
      }
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    }
  }

  useEffect(() => {
    if (!jobId) return
    let timer: ReturnType<typeof setTimeout> | null = null
    const tick = async () => {
      await pollJob()
      timer = setTimeout(tick, 1200)
    }
    tick()
    return () => { if (timer) clearTimeout(timer) }
  }, [jobId])

  async function review(assetId: number, state: 'approved' | 'rejected') {
    if (!hasPermission('asset.review')) return
    await reviewMutation.mutateAsync({ assetId, state })
  }

  async function setPrimary(assetId: number) {
    if (!hasPermission('asset.review')) return
    await setPrimaryMutation.mutateAsync({ assetId })
  }

  if (!product && (productQuery.isLoading || !id)) {
    return (
      <div className="container">
        <h2>Produkt</h2>
        {err && <div className="error">{err}</div>}
        <div className="muted">Lädt…</div>
      </div>
    )
  }

  if (!product) {
    return (
      <div className="container">
        <h2>Produkt</h2>
        {err && <div className="error">{err}</div>}
        <div className="muted">Produktdaten nicht verfügbar.</div>
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
      {productQuery.error && !err && <div className="error">{getErrorMessage(productQuery.error)}</div>}

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
                {PRODUCT_STATUS_OPTIONS.map(option => (
                  <option key={option} value={option}>{option}</option>
                ))}
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
                <td><span className="pill">{t.txType}</span></td>
                <td>{t.txDate}</td>
                <td>{t.amount ?? ''} {t.currency}</td>
                <td className="muted small">{t.note}</td>
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
