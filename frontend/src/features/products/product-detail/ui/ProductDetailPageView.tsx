import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiFetch } from '../../../../api'
import { PRODUCT_STATUS_OPTIONS } from '../../../../entities/product/model'
import type { ImageSearchJobDto } from '../../../../shared/api/contracts'
import { parseImageSearchJobDto } from '../../../../shared/api/validators'
import {
  useProductAssetsQuery,
  useProductDetailQuery,
  useProductTransactionsQuery,
  useReviewAssetMutation,
  useSetPrimaryAssetMutation,
} from '../../../../shared/api/queries/products'
import { useAuthz } from '../../../../shared/hooks/useAuthz'
import { getErrorMessage } from '../../../../shared/lib/errors'
import { ListSkeleton } from '../../../../shared/ui/states/ListSkeleton'
import { AssetCard } from './AssetCard'
import { useThumb } from './useThumb'

type ValueHistoryEntry = {
  id: string
  date: string
  value: number
  currency: string
  source: string
}

type ContentItemLink = {
  id: string
  title: string | null
  status: string
  platform: string
  type: string
  updated_at: string | null
}

type AuditItem = {
  id: string
  action: string
  description: string | null
  created_at: string
  actor_name: string | null
}

type EmailThreadRef = {
  id: string
  subject: string | null
  raw_body: string
  detected_intent: string
  updated_at: string
}

type ProductMasterForm = {
  title: string
  brand: string
  model: string
  category: string
  condition: string
  storage_location: string
  serial_number: string
  purchase_price: string
  purchase_date: string
  current_value: string
  currency: string
  notes_md: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : []
}

function parsePageItems(input: unknown): unknown[] {
  if (!isRecord(input)) return []
  return asArray(input.items)
}

function formatDate(value?: string | null): string {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleString('de-DE')
  } catch {
    return value
  }
}

function initialMasterForm(): ProductMasterForm {
  return {
    title: '',
    brand: '',
    model: '',
    category: '',
    condition: 'good',
    storage_location: '',
    serial_number: '',
    purchase_price: '',
    purchase_date: '',
    current_value: '',
    currency: 'EUR',
    notes_md: '',
  }
}

export default function ProductDetailPageView() {
  const { id } = useParams()
  const { hasPermission } = useAuthz()

  const [err, setErr] = useState<string | null>(null)
  const [masterSaving, setMasterSaving] = useState(false)
  const [masterForm, setMasterForm] = useState<ProductMasterForm>(initialMasterForm)

  const [status, setStatus] = useState('active')
  const [txDate, setTxDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [amount, setAmount] = useState('')
  const [statusSaving, setStatusSaving] = useState(false)

  const [valueHistory, setValueHistory] = useState<ValueHistoryEntry[]>([])
  const [vhDate, setVhDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [vhValue, setVhValue] = useState('')
  const [vhCurrency, setVhCurrency] = useState('EUR')
  const [vhSaving, setVhSaving] = useState(false)

  const [contentLinks, setContentLinks] = useState<ContentItemLink[]>([])
  const [contentTitle, setContentTitle] = useState('')
  const [contentSaving, setContentSaving] = useState(false)

  const [auditTimeline, setAuditTimeline] = useState<AuditItem[]>([])
  const [emailRefs, setEmailRefs] = useState<EmailThreadRef[]>([])
  const [workspaceLoading, setWorkspaceLoading] = useState(false)

  const [imageQuery, setImageQuery] = useState('')
  const [imageSource, setImageSource] = useState('auto')
  const [jobId, setJobId] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<string | null>(null)
  const [jobResult, setJobResult] = useState<ImageSearchJobDto['result']>(null)

  const productQuery = useProductDetailQuery(id)
  const assetsQuery = useProductAssetsQuery(id)
  const transactionsQuery = useProductTransactionsQuery(id)

  const reviewMutation = useReviewAssetMutation(id)
  const setPrimaryMutation = useSetPrimaryAssetMutation(id)

  const product = productQuery.data ?? null
  const assets = assetsQuery.data ?? []
  const [optimisticAssets, setOptimisticAssets] = useState<typeof assets | null>(null)
  const txs = transactionsQuery.data ?? []
  const effectiveAssets = optimisticAssets ?? assets

  const canWriteProduct = hasPermission('product.write')
  const canUploadAsset = hasPermission('asset.upload')
  const canReviewAsset = hasPermission('asset.review')
  const canSearchImages = hasPermission('image.search')
  const canReadContent = hasPermission('content.read') || hasPermission('content.manage')
  const canManageContent = hasPermission('content.manage')
  const canViewAudit = hasPermission('audit.view')
  const canReadEmail = hasPermission('email.read')

  const primary = useMemo(() => {
    const approved = effectiveAssets.filter(asset => asset.reviewState === 'approved')
    return approved.find(asset => asset.isPrimary) || approved[0] || null
  }, [effectiveAssets])
  const primaryThumb = useThumb(primary ? String(primary.id) : null)

  useEffect(() => {
    if (!product) return
    setMasterForm({
      title: product.title || '',
      brand: product.brand || '',
      model: product.model || '',
      category: '',
      condition: product.condition || 'good',
      storage_location: '',
      serial_number: '',
      purchase_price: '',
      purchase_date: '',
      current_value: product.currentValue != null ? String(product.currentValue) : '',
      currency: 'EUR',
      notes_md: product.notes || '',
    })
    setStatus(product.status)
    if (!imageQuery) {
      const q = [product.brand, product.model, product.title].filter(Boolean).join(' ')
      setImageQuery(q)
    }
  }, [product])

  async function loadWorkspaceData() {
    if (!id || !product) return
    try {
      setErr(null)
      setWorkspaceLoading(true)

      const vhRaw = await apiFetch<unknown>(`/products/${id}/value_history`)

      setValueHistory(
        asArray(vhRaw)
          .map(item => {
            if (!isRecord(item)) return null
            return {
              id: String(item.id || ''),
              date: String(item.date || ''),
              value: typeof item.value === 'number' ? item.value : Number(item.value ?? 0),
              currency: String(item.currency || 'EUR'),
              source: String(item.source || 'manual'),
            }
          })
          .filter((item): item is ValueHistoryEntry => Boolean(item && item.id))
      )

      const loadDeferred = async () => {
        const contentRaw = canReadContent
          ? await apiFetch<unknown>(`/content/items?product_id=${id}&limit=12&offset=0&sort_by=updated_at&sort_order=desc`)
          : null
        const auditRaw = canViewAudit
          ? await apiFetch<unknown>(`/audit?entity_type=product&entity_id=${id}&limit=12&offset=0&sort_by=created_at&sort_order=desc`)
          : null
        const emailRaw = canReadEmail
          ? await apiFetch<unknown>('/email/threads?limit=20&offset=0&sort_by=updated_at&sort_order=desc')
          : null

        const contentItems = parsePageItems(contentRaw)
        setContentLinks(
          contentItems
            .map(item => {
              if (!isRecord(item)) return null
              return {
                id: String(item.id || ''),
                title: typeof item.title === 'string' ? item.title : null,
                status: String(item.status || 'unknown'),
                platform: String(item.platform || 'unknown'),
                type: String(item.type || 'unknown'),
                updated_at: typeof item.updated_at === 'string' ? item.updated_at : null,
              }
            })
            .filter((item): item is ContentItemLink => Boolean(item && item.id))
        )

        const audits = parsePageItems(auditRaw)
        setAuditTimeline(
          audits
            .map(item => {
              if (!isRecord(item)) return null
              return {
                id: String(item.id || ''),
                action: String(item.action || 'unknown'),
                description: typeof item.description === 'string' ? item.description : null,
                created_at: String(item.created_at || ''),
                actor_name: typeof item.actor_name === 'string' ? item.actor_name : null,
              }
            })
            .filter((item): item is AuditItem => Boolean(item && item.id))
        )

        const threads = parsePageItems(emailRaw)
        const keywords = [product.title, product.brand, product.model]
          .map(value => (value || '').trim().toLowerCase())
          .filter(value => value.length >= 3)

        const relatedThreads = threads
          .map(item => {
            if (!isRecord(item)) return null
            return {
              id: String(item.id || ''),
              subject: typeof item.subject === 'string' ? item.subject : null,
              raw_body: String(item.raw_body || ''),
              detected_intent: String(item.detected_intent || 'unknown'),
              updated_at: String(item.updated_at || ''),
            }
          })
          .filter((item): item is EmailThreadRef => Boolean(item && item.id))
          .filter(thread => {
            if (!keywords.length) return false
            const hay = `${thread.subject || ''} ${thread.raw_body}`.toLowerCase()
            return keywords.some(keyword => hay.includes(keyword))
          })
          .slice(0, 10)

        setEmailRefs(relatedThreads)
      }

      if ('requestIdleCallback' in window) {
        ;(window as Window & { requestIdleCallback: (callback: () => void) => number }).requestIdleCallback(() => {
          void loadDeferred()
        })
      } else {
        setTimeout(() => {
          void loadDeferred()
        }, 300)
      }
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setWorkspaceLoading(false)
    }
  }

  useEffect(() => {
    void loadWorkspaceData()
  }, [id, product?.id, canReadContent, canViewAudit, canReadEmail])

  async function saveMasterData() {
    if (!id || !canWriteProduct) return
    setMasterSaving(true)
    try {
      setErr(null)
      await apiFetch(`/products/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          title: masterForm.title.trim(),
          brand: masterForm.brand.trim() || null,
          model: masterForm.model.trim() || null,
          category: masterForm.category.trim() || null,
          condition: masterForm.condition,
          storage_location: masterForm.storage_location.trim() || null,
          serial_number: masterForm.serial_number.trim() || null,
          purchase_price: masterForm.purchase_price ? Number(masterForm.purchase_price.replace(',', '.')) : null,
          purchase_date: masterForm.purchase_date || null,
          current_value: masterForm.current_value ? Number(masterForm.current_value.replace(',', '.')) : null,
          currency: masterForm.currency.trim() || 'EUR',
          notes_md: masterForm.notes_md || null,
        }),
      })
      await productQuery.refetch()
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setMasterSaving(false)
    }
  }

  async function applyStatusChange() {
    if (!id || !canWriteProduct) return
    setStatusSaving(true)
    try {
      setErr(null)
      await apiFetch(`/products/${id}/status`, {
        method: 'POST',
        body: JSON.stringify({
          status,
          date: txDate,
          amount: amount ? Number(amount.replace(',', '.')) : null,
        }),
      })
      setAmount('')
      await Promise.all([productQuery.refetch(), transactionsQuery.refetch(), loadWorkspaceData()])
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setStatusSaving(false)
    }
  }

  async function addValueEntry() {
    if (!id || !canWriteProduct || !vhValue) return
    setVhSaving(true)
    try {
      setErr(null)
      await apiFetch(`/products/${id}/value_history`, {
        method: 'POST',
        body: JSON.stringify({
          date: vhDate,
          value: Number(vhValue.replace(',', '.')),
          currency: vhCurrency || 'EUR',
          source: 'manual',
        }),
      })
      setVhValue('')
      await Promise.all([loadWorkspaceData(), productQuery.refetch()])
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setVhSaving(false)
    }
  }

  async function createContentReference() {
    if (!id || !canManageContent || !contentTitle.trim()) return
    setContentSaving(true)
    try {
      setErr(null)
      await apiFetch('/content/items', {
        method: 'POST',
        body: JSON.stringify({
          product_id: id,
          title: contentTitle.trim(),
          platform: 'youtube',
          type: 'review',
          status: 'idea',
        }),
      })
      setContentTitle('')
      await loadWorkspaceData()
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setContentSaving(false)
    }
  }

  async function upload(file: File) {
    if (!id || !canUploadAsset) return
    try {
      setErr(null)
      const form = new FormData()
      form.append('file', file)
      form.append('owner_type', 'product')
      form.append('owner_id', id)
      await fetch('/api/assets/upload', { method: 'POST', body: form, credentials: 'include' })
      await Promise.all([assetsQuery.refetch(), loadWorkspaceData()])
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    }
  }

  async function startImageHunt() {
    if (!id || !canSearchImages) return
    try {
      setErr(null)
      setJobResult(null)
      setJobStatus('queued')
      const response = await apiFetch<{ job_id?: string | number }>('/images/search', {
        method: 'POST',
        body: JSON.stringify({
          product_id: id,
          query: imageQuery,
          max_results: 12,
          source: imageSource,
        }),
      })
      if (typeof response.job_id === 'string' || typeof response.job_id === 'number') {
        setJobId(String(response.job_id))
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
      const result = parseImageSearchJobDto(await apiFetch<unknown>(`/images/jobs/${jobId}`))
      setJobStatus(result.status)
      if (result.status === 'finished') {
        setJobResult(result.result)
        await Promise.all([assetsQuery.refetch(), loadWorkspaceData()])
      }
      if (result.status === 'failed') {
        setErr(result.error || 'Job failed')
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
    void tick()
    return () => {
      if (timer) clearTimeout(timer)
    }
  }, [jobId])

  async function review(assetId: number, state: 'approved' | 'rejected') {
    if (!canReviewAsset) return
    const prev = optimisticAssets ?? assets
    setOptimisticAssets(
      prev.map(asset =>
        asset.id === assetId
          ? { ...asset, reviewState: state }
          : asset
      )
    )
    try {
      await reviewMutation.mutateAsync({ assetId, state })
      await loadWorkspaceData()
    } catch (e: unknown) {
      setOptimisticAssets(prev)
      setErr(getErrorMessage(e))
    } finally {
      setOptimisticAssets(null)
    }
  }

  async function setPrimary(assetId: number) {
    if (!canReviewAsset) return
    const prev = optimisticAssets ?? assets
    setOptimisticAssets(
      prev.map(asset => ({
        ...asset,
        isPrimary: asset.id === assetId,
      }))
    )
    try {
      await setPrimaryMutation.mutateAsync({ assetId })
      await loadWorkspaceData()
    } catch (e: unknown) {
      setOptimisticAssets(prev)
      setErr(getErrorMessage(e))
    } finally {
      setOptimisticAssets(null)
    }
  }

  if (!product && (productQuery.isLoading || !id)) {
    return (
      <div className="container">
        <h2>Produkt</h2>
        <div className="card section-gap">
          <ListSkeleton rows={8} />
        </div>
      </div>
    )
  }

  if (!product) {
    return (
      <div className="container">
        <h2>Produkt</h2>
        <div className="muted">Produktdaten nicht verfügbar.</div>
      </div>
    )
  }

  return (
    <div className="container stack">
      <div className="page-header">
        <div>
          <h2 className="page-title">Smart Product Workspace</h2>
          <div className="page-subtitle">Alle produktbezogenen Aufgaben, Daten und Bezüge in einer Oberfläche.</div>
        </div>
        <span className="muted small">ID {product.id}</span>
      </div>

      <div className="context-nav">
        <a className="context-link" href="#stammdaten">Stammdaten</a>
        <a className="context-link" href="#assets">Assets</a>
        <a className="context-link" href="#wert">Wertverlauf</a>
        <a className="context-link" href="#content">Content</a>
        <a className="context-link" href="#audit">Audit</a>
        <a className="context-link" href="#email">E-Mail</a>
      </div>

      <section className="card" id="quick-actions">
        <div className="card-head">
          <h3>Quick Actions</h3>
        </div>
        <div className="control-row">
          <Link className="btn" to="/operations">Operations Inbox</Link>
          <Link className="btn" to="/assets">Asset Reviews</Link>
          <Link className="btn" to="/content">Content Plan</Link>
          <Link className="btn" to="/email">Communication</Link>
          <button className="btn primary" onClick={() => {
            setContentTitle(prev => prev || `${product.title} Review`)
          }} disabled={!canManageContent}>
            Content-Bezug vorbereiten
          </button>
        </div>
      </section>

      {err && <div className="error">{err}</div>}

      <section className="card" id="stammdaten">
        <div className="card-head">
          <h3>Stammdaten</h3>
          <button className="btn primary" onClick={saveMasterData} disabled={!canWriteProduct || masterSaving}>
            {masterSaving ? 'Speichert…' : 'Stammdaten speichern'}
          </button>
        </div>

        <div className="grid deal-fields-grid-large">
          <div>
            <div className="field-label">Titel</div>
            <input className="w100" value={masterForm.title} onChange={event => setMasterForm(prev => ({ ...prev, title: event.target.value }))} />
          </div>
          <div>
            <div className="field-label">Brand</div>
            <input className="w100" value={masterForm.brand} onChange={event => setMasterForm(prev => ({ ...prev, brand: event.target.value }))} />
          </div>
          <div>
            <div className="field-label">Model</div>
            <input className="w100" value={masterForm.model} onChange={event => setMasterForm(prev => ({ ...prev, model: event.target.value }))} />
          </div>
          <div>
            <div className="field-label">Kategorie</div>
            <input className="w100" value={masterForm.category} onChange={event => setMasterForm(prev => ({ ...prev, category: event.target.value }))} />
          </div>
          <div>
            <div className="field-label">Condition</div>
            <select className="w100" value={masterForm.condition} onChange={event => setMasterForm(prev => ({ ...prev, condition: event.target.value }))}>
              <option value="new">new</option>
              <option value="very_good">very_good</option>
              <option value="good">good</option>
              <option value="ok">ok</option>
              <option value="broken">broken</option>
            </select>
          </div>
          <div>
            <div className="field-label">Storage</div>
            <input className="w100" value={masterForm.storage_location} onChange={event => setMasterForm(prev => ({ ...prev, storage_location: event.target.value }))} />
          </div>
          <div>
            <div className="field-label">Seriennummer</div>
            <input className="w100" value={masterForm.serial_number} onChange={event => setMasterForm(prev => ({ ...prev, serial_number: event.target.value }))} />
          </div>
          <div>
            <div className="field-label">Währung</div>
            <input className="w100" value={masterForm.currency} onChange={event => setMasterForm(prev => ({ ...prev, currency: event.target.value }))} />
          </div>
          <div>
            <div className="field-label">Kaufpreis</div>
            <input className="w100" value={masterForm.purchase_price} onChange={event => setMasterForm(prev => ({ ...prev, purchase_price: event.target.value }))} />
          </div>
          <div>
            <div className="field-label">Kaufdatum</div>
            <input className="w100" type="date" value={masterForm.purchase_date} onChange={event => setMasterForm(prev => ({ ...prev, purchase_date: event.target.value }))} />
          </div>
          <div>
            <div className="field-label">Aktueller Wert</div>
            <input className="w100" value={masterForm.current_value} onChange={event => setMasterForm(prev => ({ ...prev, current_value: event.target.value }))} />
          </div>
        </div>

        <div className="section-gap">
          <div className="field-label">Notizen</div>
          <textarea rows={6} value={masterForm.notes_md} onChange={event => setMasterForm(prev => ({ ...prev, notes_md: event.target.value }))} />
        </div>

        <hr />

        <div className="row">
          <div className="grow">
            <div className="field-label">Status</div>
            <select className="w100" value={status} onChange={event => setStatus(event.target.value)}>
              {PRODUCT_STATUS_OPTIONS.map(option => (
                <option key={option} value={option}>{option}</option>
              ))}
            </select>
          </div>
          <div>
            <div className="field-label">Datum</div>
            <input type="date" value={txDate} onChange={event => setTxDate(event.target.value)} />
          </div>
          <div>
            <div className="field-label">Betrag</div>
            <input value={amount} onChange={event => setAmount(event.target.value)} placeholder="z.B. 120" />
          </div>
          <button className="btn primary" onClick={applyStatusChange} disabled={!canWriteProduct || statusSaving}>
            {statusSaving ? 'Speichert…' : 'Status anwenden'}
          </button>
        </div>
      </section>

      <section className="card" id="assets">
        <div className="card-head">
          <h3>Assets am Produkt</h3>
          <span className="muted small">approve → primary</span>
        </div>

        <div className="row">
          <input type="file" disabled={!canUploadAsset} onChange={event => {
            const file = event.target.files?.[0]
            if (file) {
              void upload(file)
            }
          }} />
          <input className="grow" value={imageQuery} onChange={event => setImageQuery(event.target.value)} placeholder="Bildquelle suchen…" />
          <select value={imageSource} onChange={event => setImageSource(event.target.value)}>
            <option value="auto">auto</option>
            <option value="wikimedia">wikimedia</option>
            <option value="bing">bing</option>
            <option value="manufacturer">manufacturer</option>
          </select>
          <button className="btn" onClick={startImageHunt} disabled={!canSearchImages}>Search</button>
        </div>
        {jobStatus && <div className="muted small mt8">Job: {jobStatus}</div>}

        {primaryThumb ? <img src={primaryThumb} className="img mt12" loading="lazy" decoding="async" /> : <div className="muted mt12">Kein Preview vorhanden.</div>}

        <div className="grid mt12">
          {effectiveAssets.map(asset => (
            <AssetCard
              key={asset.id}
              asset={asset}
              canReview={canReviewAsset}
              onReview={review}
              onPrimary={setPrimary}
            />
          ))}
          {!effectiveAssets.length && <div className="muted">Keine Assets.</div>}
        </div>
      </section>

      <section className="card" id="wert">
        <div className="card-head">
          <h3>Wertverlauf & Transaktionen</h3>
        </div>

        <div className="row">
          <input type="date" value={vhDate} onChange={event => setVhDate(event.target.value)} />
          <input value={vhValue} onChange={event => setVhValue(event.target.value)} placeholder="Wert" />
          <input value={vhCurrency} onChange={event => setVhCurrency(event.target.value)} placeholder="Währung" />
          <button className="btn" onClick={addValueEntry} disabled={!canWriteProduct || !vhValue || vhSaving}>
            {vhSaving ? 'Speichert…' : 'Wertpunkt hinzufügen'}
          </button>
        </div>

        <div className="grid mt12">
          <div className="card tight">
            <div className="title-strong">Wertverlauf</div>
            {workspaceLoading && !valueHistory.length && <ListSkeleton rows={3} />}
            {valueHistory.map(entry => (
              <div key={entry.id} className="row between mt8">
                <span>{entry.date}</span>
                <span>{entry.value} {entry.currency}</span>
                <span className="muted small">{entry.source}</span>
              </div>
            ))}
            {!workspaceLoading && !valueHistory.length && <div className="muted mt8">Keine Werteinträge.</div>}
          </div>
          <div className="card tight">
            <div className="title-strong">Transaktionen</div>
            {txs.map(tx => (
              <div key={tx.id} className="row between mt8">
                <span>{tx.txType}</span>
                <span>{tx.txDate}</span>
                <span>{tx.amount ?? ''} {tx.currency}</span>
              </div>
            ))}
            {!txs.length && <div className="muted mt8">Keine Transaktionen.</div>}
          </div>
        </div>
      </section>

      <section className="card" id="content">
        <div className="card-head">
          <h3>Content-Bezüge</h3>
          <Link className="btn" to="/content">Im Content-Modul öffnen</Link>
        </div>

        <div className="row">
          <input
            className="grow"
            value={contentTitle}
            onChange={event => setContentTitle(event.target.value)}
            placeholder="Neuer Content-Bezug Titel…"
          />
          <button className="btn primary" onClick={createContentReference} disabled={!canManageContent || !contentTitle.trim() || contentSaving}>
            {contentSaving ? 'Erstellt…' : 'Bezug anlegen'}
          </button>
        </div>

        <table className="status-table mt12">
          <thead>
            <tr>
              <th>Titel</th>
              <th>Status</th>
              <th>Plattform</th>
              <th>Typ</th>
              <th>Aktualisiert</th>
            </tr>
          </thead>
          <tbody>
            {workspaceLoading && !contentLinks.length && (
              <tr>
                <td colSpan={5}><ListSkeleton rows={2} /></td>
              </tr>
            )}
            {contentLinks.map(item => (
              <tr key={item.id}>
                <td>{item.title || 'Ohne Titel'}</td>
                <td>{item.status}</td>
                <td>{item.platform}</td>
                <td>{item.type}</td>
                <td>{formatDate(item.updated_at)}</td>
              </tr>
            ))}
            {!workspaceLoading && !contentLinks.length && (
              <tr>
                <td colSpan={5} className="muted">Keine Content-Bezüge vorhanden.</td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      <section className="card" id="audit">
        <div className="card-head">
          <h3>Audit-Timeline (Produktebene)</h3>
          {canViewAudit ? <Link className="btn" to="/audit">Vollständiges Audit</Link> : null}
        </div>

        {!canViewAudit && <div className="muted">Keine Berechtigung für Audit-Timeline.</div>}

        {canViewAudit && (
          <div className="stack">
            {workspaceLoading && !auditTimeline.length && <ListSkeleton rows={3} />}
            {auditTimeline.map(item => (
              <div className="card tight" key={item.id}>
                <div className="row between">
                  <strong>{item.action}</strong>
                  <span className="muted small">{formatDate(item.created_at)}</span>
                </div>
                <div className="muted small">{item.description || '—'}</div>
                <div className="muted small">Akteur: {item.actor_name || 'system'}</div>
              </div>
            ))}
            {!workspaceLoading && !auditTimeline.length && <div className="muted">Keine produktbezogenen Audit-Einträge.</div>}
          </div>
        )}
      </section>

      <section className="card" id="email">
        <div className="card-head">
          <h3>E-Mail-Bezug zum Produkt</h3>
          <Link className="btn" to="/email">Communication öffnen</Link>
        </div>

        {!canReadEmail && <div className="muted">Keine Berechtigung für E-Mail-Bezug.</div>}

        {canReadEmail && (
          <table className="status-table">
            <thead>
              <tr>
                <th>Betreff</th>
                <th>Intent</th>
                <th>Aktualisiert</th>
              </tr>
            </thead>
            <tbody>
              {workspaceLoading && !emailRefs.length && (
                <tr>
                  <td colSpan={3}><ListSkeleton rows={2} /></td>
                </tr>
              )}
              {emailRefs.map(thread => (
                <tr key={thread.id}>
                  <td>{thread.subject || 'Ohne Betreff'}</td>
                  <td>{thread.detected_intent}</td>
                  <td>{formatDate(thread.updated_at)}</td>
                </tr>
              ))}
              {!workspaceLoading && !emailRefs.length && (
                <tr>
                  <td colSpan={3} className="muted">Keine direkt erkannten E-Mail-Bezüge.</td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </section>

      {jobResult?.candidates?.length ? (
        <div className="card">
          <div className="muted small">Letzte Bildsuche: {jobResult.query} • {jobResult.count} Kandidaten</div>
        </div>
      ) : null}
    </div>
  )
}
