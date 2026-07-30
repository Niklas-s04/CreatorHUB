import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
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
import { useI18n } from '../../../../shared/i18n/i18n'
import { getErrorMessage } from '../../../../shared/lib/errors'
import { ListSkeleton } from '../../../../shared/ui/states/ListSkeleton'
import {
  buildProductMasterPatch,
  initialMasterForm,
  masterFormsEqual,
  productToMasterForm,
} from '../model/productMasterForm'
import { useImageSearchJobPolling } from '../model/useImageSearchJobPolling'
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
    return new Date(value).toLocaleString()
  } catch {
    return value
  }
}

export default function ProductDetailPageView() {
  const { id } = useParams()
  const { hasPermission } = useAuthz()
  const { language } = useI18n()

  const [err, setErr] = useState<string | null>(null)
  const [masterSaving, setMasterSaving] = useState(false)
  const [masterForm, setMasterForm] = useState(initialMasterForm)
  const [masterBaseline, setMasterBaseline] = useState(initialMasterForm)
  const masterProductIdRef = useRef<string | null>(null)
  const contentTitleInputRef = useRef<HTMLInputElement>(null)

  const [status, setStatus] = useState('active')
  const [statusBaseline, setStatusBaseline] = useState('active')
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
    const approved = effectiveAssets.filter((asset) => asset.reviewState === 'approved')
    return approved.find((asset) => asset.isPrimary) || approved[0] || null
  }, [effectiveAssets])
  const primaryThumb = useThumb(primary ? String(primary.id) : null)
  const masterDirty = !masterFormsEqual(masterForm, masterBaseline)
  const statusDirty = status !== statusBaseline

  useEffect(() => {
    if (!product) return

    const nextForm = productToMasterForm(product)
    const productChanged = masterProductIdRef.current !== product.id

    if (productChanged || !masterDirty) {
      masterProductIdRef.current = product.id
      setMasterForm(nextForm)
      setMasterBaseline(nextForm)
    }

    if (productChanged || !statusDirty) {
      setStatus(product.status)
      setStatusBaseline(product.status)
    }
    if (productChanged) {
      const q = [product.brand, product.model, product.title].filter(Boolean).join(' ')
      setImageQuery(q)
    }
  }, [masterDirty, product, statusDirty])

  const loadWorkspaceData = useCallback(async () => {
    if (!id || !product) return
    try {
      setErr(null)
      setWorkspaceLoading(true)

      const vhRaw = await apiFetch<unknown>(`/products/${id}/value_history`)

      setValueHistory(
        asArray(vhRaw)
          .map((item) => {
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
          ? await apiFetch<unknown>(
              `/content/items?product_id=${id}&limit=12&offset=0&sort_by=updated_at&sort_order=desc`
            )
          : null
        const auditRaw = canViewAudit
          ? await apiFetch<unknown>(
              `/audit?entity_type=product&entity_id=${id}&limit=12&offset=0&sort_by=created_at&sort_order=desc`
            )
          : null
        const emailRaw = canReadEmail
          ? await apiFetch<unknown>(
              '/email/threads?limit=20&offset=0&sort_by=updated_at&sort_order=desc'
            )
          : null

        const contentItems = parsePageItems(contentRaw)
        setContentLinks(
          contentItems
            .map((item) => {
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
            .map((item) => {
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
          .map((value) => (value || '').trim().toLowerCase())
          .filter((value) => value.length >= 3)

        const relatedThreads = threads
          .map((item) => {
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
          .filter((thread) => {
            if (!keywords.length) return false
            const hay = `${thread.subject || ''} ${thread.raw_body}`.toLowerCase()
            return keywords.some((keyword) => hay.includes(keyword))
          })
          .slice(0, 10)

        setEmailRefs(relatedThreads)
      }

      if ('requestIdleCallback' in window) {
        ;(
          window as Window & { requestIdleCallback: (callback: () => void) => number }
        ).requestIdleCallback(() => {
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
  }, [canReadContent, canReadEmail, canViewAudit, id, product])

  useEffect(() => {
    void loadWorkspaceData()
  }, [loadWorkspaceData])

  async function saveMasterData() {
    if (!id || !canWriteProduct || !masterDirty) return
    const submittedForm = { ...masterForm }

    setMasterSaving(true)
    try {
      setErr(null)
      const patch = buildProductMasterPatch(submittedForm, masterBaseline)
      if (!Object.keys(patch).length) return
      await apiFetch(`/products/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      })
      setMasterBaseline(submittedForm)
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
      setStatusBaseline(status)
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
      await apiFetch('/assets/upload', { method: 'POST', body: form })
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
        setErr(
          language === 'en'
            ? 'Invalid job response from server'
            : 'Ungültige Job-Antwort vom Server'
        )
      }
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    }
  }

  useImageSearchJobPolling({
    jobId,
    poll: async (currentJobId) =>
      parseImageSearchJobDto(await apiFetch<unknown>(`/images/jobs/${currentJobId}`)),
    onStatus: setJobStatus,
    onFinished: (result) => {
      setJobResult(result)
      setJobId(null)
      void assetsQuery.refetch()
    },
    onFailed: (error) => {
      setErr(error || 'Job failed')
      setJobId(null)
    },
    onError: (error) => {
      setErr(getErrorMessage(error))
      setJobId(null)
    },
  })

  function prepareContentReference() {
    document.getElementById('content')?.scrollIntoView?.({
      behavior: 'smooth',
      block: 'start',
    })
    contentTitleInputRef.current?.focus()
  }

  async function review(assetId: string, state: 'approved' | 'rejected') {
    if (!canReviewAsset) return
    const prev = optimisticAssets ?? assets
    setOptimisticAssets(
      prev.map((asset) => (asset.id === assetId ? { ...asset, reviewState: state } : asset))
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

  async function setPrimary(assetId: string) {
    if (!canReviewAsset) return
    const prev = optimisticAssets ?? assets
    setOptimisticAssets(
      prev.map((asset) => ({
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
        <h2>{language === 'en' ? 'Product' : 'Produkt'}</h2>
        <div className="card section-gap">
          <ListSkeleton rows={8} />
        </div>
      </div>
    )
  }

  if (!product) {
    return (
      <div className="container">
        <h2>{language === 'en' ? 'Product' : 'Produkt'}</h2>
        <div className="muted">
          {language === 'en' ? 'Product data not available.' : 'Produktdaten nicht verfügbar.'}
        </div>
      </div>
    )
  }

  return (
    <div className="container stack">
      <div className="page-header">
        <div>
          <h2 className="page-title">Smart Product Workspace</h2>
          <div className="page-subtitle">
            {language === 'en'
              ? 'All product-related tasks, data and relationships in one workspace.'
              : 'Alle produktbezogenen Aufgaben, Daten und Bezüge in einer Oberfläche.'}
          </div>
        </div>
        <span className="muted small">ID {product.id}</span>
      </div>

      <div className="context-nav">
        <a className="context-link" href="#stammdaten">
          {language === 'en' ? 'Master data' : 'Stammdaten'}
        </a>
        <a className="context-link" href="#assets">
          Assets
        </a>
        <a className="context-link" href="#wert">
          {language === 'en' ? 'Value history' : 'Wertverlauf'}
        </a>
        <a className="context-link" href="#content">
          Content
        </a>
        <a className="context-link" href="#audit">
          Audit
        </a>
        <a className="context-link" href="#email">
          {language === 'en' ? 'Email' : 'E-Mail'}
        </a>
      </div>

      <section className="card" id="quick-actions">
        <div className="card-head">
          <h3>Quick Actions</h3>
        </div>
        <div className="control-row">
          <Link className="btn" to="/operations">
            Operations Inbox
          </Link>
          <Link className="btn" to="/assets">
            Asset Reviews
          </Link>
          <Link className="btn" to="/content">
            Content Plan
          </Link>
          <Link className="btn" to="/email">
            Communication
          </Link>
          <button
            className="btn primary"
            onClick={prepareContentReference}
            disabled={!canManageContent}
          >
            {language === 'en' ? 'Prepare content reference' : 'Content-Bezug vorbereiten'}
          </button>
        </div>
      </section>

      {err && <div className="error">{err}</div>}

      <section className="card" id="stammdaten">
        <div className="card-head">
          <h3>{language === 'en' ? 'Master data' : 'Stammdaten'}</h3>
          <button
            className="btn primary"
            onClick={saveMasterData}
            disabled={!canWriteProduct || masterSaving || !masterDirty}
          >
            {masterSaving
              ? language === 'en'
                ? 'Saving…'
                : 'Speichert…'
              : language === 'en'
                ? 'Save master data'
                : 'Stammdaten speichern'}
          </button>
        </div>

        <div className="grid deal-fields-grid-large">
          <div>
            <div className="field-label">{language === 'en' ? 'Title' : 'Titel'}</div>
            <input
              aria-label={language === 'en' ? 'Title' : 'Titel'}
              className="w100"
              value={masterForm.title}
              onChange={(event) =>
                setMasterForm((prev) => ({ ...prev, title: event.target.value }))
              }
            />
          </div>
          <div>
            <div className="field-label">Brand</div>
            <input
              className="w100"
              value={masterForm.brand}
              onChange={(event) =>
                setMasterForm((prev) => ({ ...prev, brand: event.target.value }))
              }
            />
          </div>
          <div>
            <div className="field-label">Model</div>
            <input
              className="w100"
              value={masterForm.model}
              onChange={(event) =>
                setMasterForm((prev) => ({ ...prev, model: event.target.value }))
              }
            />
          </div>
          <div>
            <div className="field-label">{language === 'en' ? 'Category' : 'Kategorie'}</div>
            <input
              className="w100"
              value={masterForm.category}
              onChange={(event) =>
                setMasterForm((prev) => ({ ...prev, category: event.target.value }))
              }
            />
          </div>
          <div>
            <div className="field-label">Condition</div>
            <select
              className="w100"
              value={masterForm.condition}
              onChange={(event) =>
                setMasterForm((prev) => ({ ...prev, condition: event.target.value }))
              }
            >
              <option value="new">new</option>
              <option value="very_good">very_good</option>
              <option value="good">good</option>
              <option value="ok">ok</option>
              <option value="broken">broken</option>
            </select>
          </div>
          <div>
            <div className="field-label">Storage</div>
            <input
              className="w100"
              value={masterForm.storage_location}
              onChange={(event) =>
                setMasterForm((prev) => ({ ...prev, storage_location: event.target.value }))
              }
            />
          </div>
          <div>
            <div className="field-label">
              {language === 'en' ? 'Serial number' : 'Seriennummer'}
            </div>
            <input
              className="w100"
              value={masterForm.serial_number}
              onChange={(event) =>
                setMasterForm((prev) => ({ ...prev, serial_number: event.target.value }))
              }
            />
          </div>
          <div>
            <div className="field-label">{language === 'en' ? 'Currency' : 'Währung'}</div>
            <input
              className="w100"
              value={masterForm.currency}
              onChange={(event) =>
                setMasterForm((prev) => ({ ...prev, currency: event.target.value }))
              }
            />
          </div>
          <div>
            <div className="field-label">{language === 'en' ? 'Purchase price' : 'Kaufpreis'}</div>
            <input
              className="w100"
              value={masterForm.purchase_price}
              onChange={(event) =>
                setMasterForm((prev) => ({ ...prev, purchase_price: event.target.value }))
              }
            />
          </div>
          <div>
            <div className="field-label">{language === 'en' ? 'Purchase date' : 'Kaufdatum'}</div>
            <input
              className="w100"
              type="date"
              value={masterForm.purchase_date}
              onChange={(event) =>
                setMasterForm((prev) => ({ ...prev, purchase_date: event.target.value }))
              }
            />
          </div>
          <div>
            <div className="field-label">
              {language === 'en' ? 'Current value' : 'Aktueller Wert'}
            </div>
            <input
              className="w100"
              value={masterForm.current_value}
              onChange={(event) =>
                setMasterForm((prev) => ({ ...prev, current_value: event.target.value }))
              }
            />
          </div>
        </div>

        <div className="section-gap">
          <div className="field-label">{language === 'en' ? 'Notes' : 'Notizen'}</div>
          <textarea
            aria-label={language === 'en' ? 'Notes' : 'Notizen'}
            rows={6}
            value={masterForm.notes_md}
            onChange={(event) =>
              setMasterForm((prev) => ({ ...prev, notes_md: event.target.value }))
            }
          />
        </div>

        <hr />

        <div className="row">
          <div className="grow">
            <div className="field-label">Status</div>
            <select
              className="w100"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              {PRODUCT_STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>
          <div>
            <div className="field-label">{language === 'en' ? 'Date' : 'Datum'}</div>
            <input type="date" value={txDate} onChange={(event) => setTxDate(event.target.value)} />
          </div>
          <div>
            <div className="field-label">{language === 'en' ? 'Amount' : 'Betrag'}</div>
            <input
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              placeholder={language === 'en' ? 'e.g. 120' : 'z.B. 120'}
            />
          </div>
          <button
            className="btn primary"
            onClick={applyStatusChange}
            disabled={!canWriteProduct || statusSaving}
          >
            {statusSaving
              ? language === 'en'
                ? 'Saving…'
                : 'Speichert…'
              : language === 'en'
                ? 'Apply status'
                : 'Status anwenden'}
          </button>
        </div>
      </section>

      <section className="card" id="assets">
        <div className="card-head">
          <h3>Assets am Produkt</h3>
          <span className="muted small">approve → primary</span>
        </div>

        <div className="row">
          <input
            type="file"
            disabled={!canUploadAsset}
            onChange={(event) => {
              const file = event.target.files?.[0]
              if (file) {
                void upload(file)
              }
            }}
          />
          <input
            className="grow"
            value={imageQuery}
            onChange={(event) => setImageQuery(event.target.value)}
            placeholder={language === 'en' ? 'Search image source…' : 'Bildquelle suchen…'}
          />
          <select value={imageSource} onChange={(event) => setImageSource(event.target.value)}>
            <option value="auto">auto</option>
            <option value="wikimedia">wikimedia</option>
            <option value="bing">bing</option>
            <option value="manufacturer">manufacturer</option>
          </select>
          <button className="btn" onClick={startImageHunt} disabled={!canSearchImages}>
            Search
          </button>
        </div>
        {jobStatus && <div className="muted small mt8">Job: {jobStatus}</div>}

        {primaryThumb ? (
          <img
            src={primaryThumb}
            className="img mt12"
            loading="lazy"
            decoding="async"
            fetchPriority="low"
            sizes="(max-width: 900px) 100vw, 640px"
            alt={
              product.title
                ? language === 'en'
                  ? `Preview for ${product.title}`
                  : `Preview für ${product.title}`
                : language === 'en'
                  ? 'Product preview'
                  : 'Produkt-Preview'
            }
            width={640}
            height={360}
          />
        ) : (
          <div className="muted mt12">
            {language === 'en' ? 'No preview available.' : 'Kein Preview vorhanden.'}
          </div>
        )}

        <div className="grid mt12">
          {effectiveAssets.map((asset) => (
            <AssetCard
              key={asset.id}
              asset={asset}
              canReview={canReviewAsset}
              onReview={review}
              onPrimary={setPrimary}
            />
          ))}
          {!effectiveAssets.length && (
            <div className="muted">{language === 'en' ? 'No assets.' : 'Keine Assets.'}</div>
          )}
        </div>
      </section>

      <section className="card" id="wert">
        <div className="card-head">
          <h3>Wertverlauf & Transaktionen</h3>
        </div>

        <div className="row">
          <input type="date" value={vhDate} onChange={(event) => setVhDate(event.target.value)} />
          <input
            value={vhValue}
            onChange={(event) => setVhValue(event.target.value)}
            placeholder="Wert"
          />
          <input
            value={vhCurrency}
            onChange={(event) => setVhCurrency(event.target.value)}
            placeholder={language === 'en' ? 'Currency' : 'Währung'}
          />
          <button
            className="btn"
            onClick={addValueEntry}
            disabled={!canWriteProduct || !vhValue || vhSaving}
          >
            {vhSaving
              ? language === 'en'
                ? 'Saving…'
                : 'Speichert…'
              : language === 'en'
                ? 'Add value point'
                : 'Wertpunkt hinzufügen'}
          </button>
        </div>

        <div className="grid mt12">
          <div className="card tight">
            <div className="title-strong">
              {language === 'en' ? 'Value history' : 'Wertverlauf'}
            </div>
            {workspaceLoading && !valueHistory.length && <ListSkeleton rows={3} />}
            {valueHistory.map((entry) => (
              <div key={entry.id} className="row between mt8">
                <span>{entry.date}</span>
                <span>
                  {entry.value} {entry.currency}
                </span>
                <span className="muted small">{entry.source}</span>
              </div>
            ))}
            {!workspaceLoading && !valueHistory.length && (
              <div className="muted mt8">
                {language === 'en' ? 'No value entries.' : 'Keine Werteinträge.'}
              </div>
            )}
          </div>
          <div className="card tight">
            <div className="title-strong">
              {language === 'en' ? 'Transactions' : 'Transaktionen'}
            </div>
            {txs.map((tx) => (
              <div key={tx.id} className="row between mt8">
                <span>{tx.txType}</span>
                <span>{tx.txDate}</span>
                <span>
                  {tx.amount ?? ''} {tx.currency}
                </span>
              </div>
            ))}
            {!txs.length && (
              <div className="muted mt8">
                {language === 'en' ? 'No transactions.' : 'Keine Transaktionen.'}
              </div>
            )}
          </div>
        </div>
      </section>

      <section className="card" id="content">
        <div className="card-head">
          <h3>{language === 'en' ? 'Content references' : 'Content-Bezüge'}</h3>
          <Link className="btn" to="/content">
            {language === 'en' ? 'Open in content module' : 'Im Content-Modul öffnen'}
          </Link>
        </div>

        <div className="row">
          <input
            ref={contentTitleInputRef}
            className="grow"
            value={contentTitle}
            onChange={(event) => setContentTitle(event.target.value)}
            placeholder={
              language === 'en' ? 'New content reference title…' : 'Neuer Content-Bezug Titel…'
            }
          />
          <button
            className="btn primary"
            onClick={createContentReference}
            disabled={!canManageContent || !contentTitle.trim() || contentSaving}
          >
            {contentSaving
              ? language === 'en'
                ? 'Creating…'
                : 'Erstellt…'
              : language === 'en'
                ? 'Create reference'
                : 'Bezug anlegen'}
          </button>
        </div>

        <table className="status-table mt12">
          <thead>
            <tr>
              <th>{language === 'en' ? 'Title' : 'Titel'}</th>
              <th>Status</th>
              <th>{language === 'en' ? 'Platform' : 'Plattform'}</th>
              <th>{language === 'en' ? 'Type' : 'Typ'}</th>
              <th>{language === 'en' ? 'Updated' : 'Aktualisiert'}</th>
            </tr>
          </thead>
          <tbody>
            {workspaceLoading && !contentLinks.length && (
              <tr>
                <td colSpan={5}>
                  <ListSkeleton rows={2} />
                </td>
              </tr>
            )}
            {contentLinks.map((item) => (
              <tr key={item.id}>
                <td>{item.title || (language === 'en' ? 'Untitled' : 'Ohne Titel')}</td>
                <td>{item.status}</td>
                <td>{item.platform}</td>
                <td>{item.type}</td>
                <td>{formatDate(item.updated_at)}</td>
              </tr>
            ))}
            {!workspaceLoading && !contentLinks.length && (
              <tr>
                <td colSpan={5} className="muted">
                  {language === 'en'
                    ? 'No content references available.'
                    : 'Keine Content-Bezüge vorhanden.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>

      <section className="card" id="audit">
        <div className="card-head">
          <h3>
            {language === 'en' ? 'Audit timeline (product level)' : 'Audit-Timeline (Produktebene)'}
          </h3>
          {canViewAudit ? (
            <Link className="btn" to="/audit">
              {language === 'en' ? 'Full audit' : 'Vollständiges Audit'}
            </Link>
          ) : null}
        </div>

        {!canViewAudit && (
          <div className="muted">
            {language === 'en'
              ? 'No permission for audit timeline.'
              : 'Keine Berechtigung für Audit-Timeline.'}
          </div>
        )}

        {canViewAudit && (
          <div className="stack">
            {workspaceLoading && !auditTimeline.length && <ListSkeleton rows={3} />}
            {auditTimeline.map((item) => (
              <div className="card tight" key={item.id}>
                <div className="row between">
                  <strong>{item.action}</strong>
                  <span className="muted small">{formatDate(item.created_at)}</span>
                </div>
                <div className="muted small">{item.description || '—'}</div>
                <div className="muted small">
                  {language === 'en' ? 'Actor' : 'Akteur'}: {item.actor_name || 'system'}
                </div>
              </div>
            ))}
            {!workspaceLoading && !auditTimeline.length && (
              <div className="muted">
                {language === 'en'
                  ? 'No product-related audit entries.'
                  : 'Keine produktbezogenen Audit-Einträge.'}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="card" id="email">
        <div className="card-head">
          <h3>
            {language === 'en' ? 'Email references for this product' : 'E-Mail-Bezug zum Produkt'}
          </h3>
          <Link className="btn" to="/email">
            {language === 'en' ? 'Open communication' : 'Communication öffnen'}
          </Link>
        </div>

        {!canReadEmail && (
          <div className="muted">
            {language === 'en'
              ? 'No permission for email references.'
              : 'Keine Berechtigung für E-Mail-Bezug.'}
          </div>
        )}

        {canReadEmail && (
          <table className="status-table">
            <thead>
              <tr>
                <th>Betreff</th>
                <th>{language === 'en' ? 'Subject' : 'Betreff'}</th>
                <th>Intent</th>
                <th>{language === 'en' ? 'Updated' : 'Aktualisiert'}</th>
              </tr>
            </thead>
            <tbody>
              {workspaceLoading && !emailRefs.length && (
                <tr>
                  <td colSpan={3}>
                    <ListSkeleton rows={2} />
                  </td>
                </tr>
              )}
              {emailRefs.map((thread) => (
                <tr key={thread.id}>
                  <td>{thread.subject || (language === 'en' ? 'No subject' : 'Ohne Betreff')}</td>
                  <td>{thread.detected_intent}</td>
                  <td>{formatDate(thread.updated_at)}</td>
                </tr>
              ))}
              {!workspaceLoading && !emailRefs.length && (
                <tr>
                  <td colSpan={3} className="muted">
                    {language === 'en'
                      ? 'No directly detected email references.'
                      : 'Keine direkt erkannten E-Mail-Bezüge.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </section>

      {jobResult?.candidates?.length ? (
        <div className="card">
          <div className="muted small">
            {language === 'en' ? 'Last image search' : 'Letzte Bildsuche'}: {jobResult.query} •{' '}
            {jobResult.count} {language === 'en' ? 'candidates' : 'Kandidaten'}
          </div>
        </div>
      ) : null}
    </div>
  )
}
