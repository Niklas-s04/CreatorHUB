import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiFetchBlob } from '../../../../api'
import { getErrorMessage } from '../../../../shared/lib/errors'
import { useDebouncedValue } from '../../../../shared/hooks/useDebouncedValue'
import { EmptyState } from '../../../../shared/ui/states/EmptyState'
import { ErrorState } from '../../../../shared/ui/states/ErrorState'
import { ListSkeleton } from '../../../../shared/ui/states/ListSkeleton'
import { useToast } from '../../../../shared/ui/toast/ToastProvider'
import {
  type AssetKind,
  type AssetLibraryItem,
  type AssetOwnerType,
  type LicenseFilter,
  useAssetLibraryQuery,
} from '../../../../shared/api/queries/assets'

const ownerTypeOptions: { value: '' | AssetOwnerType; label: string }[] = [
  { value: '', label: 'Alle Typen' },
  { value: 'product', label: 'Produkt' },
  { value: 'content', label: 'Content' },
  { value: 'email', label: 'Email' },
  { value: 'deal', label: 'Deal' },
]

const kindOptions: { value: '' | AssetKind; label: string }[] = [
  { value: '', label: 'Alle Formate' },
  { value: 'image', label: 'Bild' },
  { value: 'video', label: 'Video' },
  { value: 'pdf', label: 'PDF' },
  { value: 'link', label: 'Link' },
]

const licenseFilterOptions: { value: LicenseFilter; label: string }[] = [
  { value: 'any', label: 'Lizenz egal' },
  { value: 'licensed', label: 'Lizenz vorhanden' },
  { value: 'missing', label: 'Lizenz fehlt' },
]

const ownerLabels: Record<AssetOwnerType, string> = {
  product: 'Produkt',
  content: 'Content',
  email: 'Email',
  deal: 'Deal',
}

function formatBytes(size: number | null) {
  if (!size) return '–'
  if (size < 1024) return `${size} B`
  const kb = size / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  const mb = kb / 1024
  return `${mb.toFixed(1)} MB`
}

function summarizeDimension(asset: AssetLibraryItem) {
  if (!asset.width || !asset.height) return 'n/a'
  return `${asset.width}×${asset.height}`
}

function formatDate(value: string) {
  try {
    return new Date(value).toLocaleDateString('de-DE', {
      day: '2-digit', month: '2-digit', year: '2-digit'
    })
  } catch (e) {
    return value
  }
}

function hasLicense(asset: AssetLibraryItem) {
  return Boolean(asset.license_type || asset.license_url)
}

function ThumbVisibilityProbe({ assetId, onVisible }: { assetId: string; onVisible: (id: string) => void }) {
  const ref = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const node = ref.current
    if (!node) return

    const observer = new IntersectionObserver(
      entries => {
        if (!entries[0]?.isIntersecting) return
        onVisible(assetId)
        observer.disconnect()
      },
      { rootMargin: '240px 0px' }
    )

    observer.observe(node)
    return () => observer.disconnect()
  }, [assetId, onVisible])

  return <div ref={ref} className="asset-thumb-probe" aria-hidden="true" />
}

export default function AssetsPage() {
  const toast = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const [searchInput, setSearchInput] = useState(searchParams.get('q') || '')
  const [ownerType, setOwnerType] = useState<'' | AssetOwnerType>((searchParams.get('owner_type') as AssetOwnerType | '') || '')
  const [kind, setKind] = useState<'' | AssetKind>((searchParams.get('kind') as AssetKind | '') || '')
  const [approvedOnly, setApprovedOnly] = useState(searchParams.get('approved_only') !== 'false')
  const [primaryOnly, setPrimaryOnly] = useState(searchParams.get('primary_only') === 'true')
  const [licenseFilter, setLicenseFilter] = useState<LicenseFilter>((searchParams.get('license_filter') as LicenseFilter) || 'any')
  const [pageSize, setPageSize] = useState(() => {
    const parsed = Number(searchParams.get('limit') || '24')
    if (![24, 36, 60].includes(parsed)) return 24
    return parsed
  })
  const [offset, setOffset] = useState(() => Math.max(0, Number(searchParams.get('offset') || '0') || 0))
  const debouncedSearchTerm = useDebouncedValue(searchInput.trim(), 350)
  const tableAnchorRef = useRef<HTMLDivElement | null>(null)
  const [thumbs, setThumbs] = useState<Record<string, string>>({})
  const [visibleThumbIds, setVisibleThumbIds] = useState<Set<string>>(new Set())
  const [err, setErr] = useState<string | null>(null)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const thumbCacheRef = useRef<Record<string, string>>({})

  useEffect(() => {
    return () => {
      Object.values(thumbCacheRef.current).forEach(url => URL.revokeObjectURL(url))
    }
  }, [])

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    if (debouncedSearchTerm) next.set('q', debouncedSearchTerm)
    else next.delete('q')
    if (ownerType) next.set('owner_type', ownerType)
    else next.delete('owner_type')
    if (kind) next.set('kind', kind)
    else next.delete('kind')
    next.set('approved_only', approvedOnly ? 'true' : 'false')
    next.set('primary_only', primaryOnly ? 'true' : 'false')
    next.set('license_filter', licenseFilter)
    next.set('limit', String(pageSize))
    next.set('offset', String(offset))
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true })
    }
  }, [debouncedSearchTerm, ownerType, kind, approvedOnly, primaryOnly, licenseFilter, pageSize, offset, searchParams, setSearchParams])

  const assetsQuery = useAssetLibraryQuery({
    search: debouncedSearchTerm || undefined,
    ownerType: ownerType || undefined,
    kind: kind || undefined,
    approvedOnly,
    primaryOnly,
    licenseFilter,
    limit: pageSize,
    offset,
  })
  const assets = assetsQuery.data ?? []
  const loading = assetsQuery.isLoading || assetsQuery.isFetching
  const queryErr = assetsQuery.error ? getErrorMessage(assetsQuery.error) : null

  useEffect(() => {
    Object.values(thumbCacheRef.current).forEach(url => URL.revokeObjectURL(url))
    thumbCacheRef.current = {}
    setThumbs({})
    setVisibleThumbIds(() => {
      const initial = assets.filter(asset => asset.kind === 'image').slice(0, 12).map(asset => asset.id)
      return new Set(initial)
    })
  }, [assets])

  useEffect(() => {
    const images = assets.filter(a => a.kind === 'image' && visibleThumbIds.has(a.id))
    images.forEach(asset => {
      if (thumbCacheRef.current[asset.id]) return
      ;(async () => {
        try {
          const blob = await apiFetchBlob(`/assets/${asset.id}/thumb`)
          const url = URL.createObjectURL(blob)
          thumbCacheRef.current[asset.id] = url
          setThumbs(prev => ({ ...prev, [asset.id]: url }))
        } catch (error) {
          // Vorschaufehler bewusst ignorieren.
        }
      })()
    })
  }, [assets, visibleThumbIds])

  function markThumbVisible(assetId: string) {
    setVisibleThumbIds(current => {
      if (current.has(assetId)) return current
      const next = new Set(current)
      next.add(assetId)
      return next
    })
  }

  useEffect(() => {
    setOffset(0)
  }, [debouncedSearchTerm, ownerType, kind, approvedOnly, primaryOnly, licenseFilter, pageSize])

  const stats = useMemo(() => {
    const licensed = assets.filter(a => hasLicense(a)).length
    const primary = assets.filter(a => a.is_primary).length
    return { licensed, missing: Math.max(0, assets.length - licensed), primary }
  }, [assets])

  function reload() {
    void assetsQuery.refetch()
  }

  function changePage(direction: 'prev' | 'next') {
    setOffset(current => {
      if (direction === 'prev') return Math.max(0, current - pageSize)
      if (assets.length < pageSize) return current
      return current + pageSize
    })
    tableAnchorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  async function openOriginal(assetId: string) {
    setDownloadingId(assetId)
    try {
      const blob = await apiFetchBlob(`/assets/${assetId}/file`)
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank', 'noopener')
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch (e: unknown) {
      const message = `Download fehlgeschlagen: ${getErrorMessage(e)}`
      setErr(message)
      toast.error(message)
    } finally {
      setDownloadingId(curr => (curr === assetId ? null : curr))
    }
  }

  return (
    <div className="container">
      <div className="row between">
        <div>
          <h2>Mediathek</h2>
          <div className="muted">Suche, filtere und exportiere geprüfte Assets.</div>
        </div>
        <div className="control-row">
          <div className="card tight" role="status" aria-live="polite" aria-label={`Gefilterte Assets: ${assets.length}`}>
            <div className="muted small">Gefiltert</div>
            <div className="kpi">{assets.length}</div>
          </div>
          <div className="card tight">
            <div className="muted small">Lizenz ok</div>
            <div className="kpi metric-kpi">{stats.licensed}</div>
          </div>
          <div className="card tight">
            <div className="muted small">Primary</div>
            <div className="kpi metric-kpi">{stats.primary}</div>
          </div>
        </div>
      </div>

      {queryErr && (
        <ErrorState
          title="Assets konnten nicht geladen werden"
          message={queryErr}
          onRetry={reload}
        />
      )}
      {err && !queryErr && <ErrorState title="Aktion fehlgeschlagen" message={err} />}

      <div className="card asset-controls mt16">
        <div ref={tableAnchorRef} />
        <div className="control-row stretch">
          <label className="sr-only" htmlFor="assets-search">Assets suchen</label>
          <input
            id="assets-search"
            className="grow"
            placeholder="Suche (Titel, Quelle, URL)"
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
          />
          <button className="btn" onClick={reload} disabled={loading}>Refresh</button>
        </div>
        <div className="control-row">
          <label className="sr-only" htmlFor="assets-owner-type">Owner-Typ</label>
          <select id="assets-owner-type" value={ownerType} onChange={e => setOwnerType(e.target.value as AssetOwnerType | '')}>
            {ownerTypeOptions.map(opt => (
              <option key={opt.value || 'all'} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <label className="sr-only" htmlFor="assets-kind">Asset-Art</label>
          <select id="assets-kind" value={kind} onChange={e => setKind(e.target.value as AssetKind | '')}>
            {kindOptions.map(opt => (
              <option key={opt.value || 'all'} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <label className="sr-only" htmlFor="assets-license-filter">Lizenzfilter</label>
          <select id="assets-license-filter" value={licenseFilter} onChange={e => setLicenseFilter(e.target.value as LicenseFilter)}>
            {licenseFilterOptions.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <label className="sr-only" htmlFor="assets-page-size">Seitenlimit</label>
          <select id="assets-page-size" value={String(pageSize)} onChange={e => setPageSize(Number(e.target.value))}>
            <option value="24">24 / Seite</option>
            <option value="36">36 / Seite</option>
            <option value="60">60 / Seite</option>
          </select>
        </div>
        <div className="asset-checkboxes">
          <label className="filter-check">
            <input type="checkbox" checked={approvedOnly} onChange={e => setApprovedOnly(e.target.checked)} />
            Nur approved
          </label>
          <label className="filter-check">
            <input type="checkbox" checked={primaryOnly} onChange={e => setPrimaryOnly(e.target.checked)} />
            Nur Primary
          </label>
        </div>
      </div>

      {loading && assets.length === 0 && <ListSkeleton rows={6} />}

      <div className="asset-grid mt16">
        {assets.map(asset => {
          const thumbUrl = thumbs[asset.id]
          const licenseOk = hasLicense(asset)
          return (
            <div key={asset.id} id={`asset-${asset.id}`} className="asset-card">
              <div className="asset-cover">
                {asset.kind === 'image' && !thumbUrl && <ThumbVisibilityProbe assetId={asset.id} onVisible={markThumbVisible} />}
                {asset.kind === 'image' && thumbUrl && (
                  <img
                    src={thumbUrl}
                    alt={asset.title || 'Asset preview'}
                    loading="lazy"
                    decoding="async"
                    fetchPriority="low"
                    sizes="(max-width: 900px) 100vw, 320px"
                    width={asset.width || 640}
                    height={asset.height || 360}
                  />
                )}
                {asset.kind === 'image' && !thumbUrl && (
                  <div className="asset-placeholder">Preview lädt…</div>
                )}
                {asset.kind !== 'image' && (
                  <div className="asset-placeholder">{asset.kind.toUpperCase()}</div>
                )}
                {asset.is_primary && <span className="asset-flag primary">Primary</span>}
                {asset.review_state !== 'approved' && (
                  <span className={`asset-flag ${asset.review_state}`}>{asset.review_state}</span>
                )}
              </div>
              <div className="asset-card-body">
                <div className="row between">
                  <strong>{asset.title || 'Ohne Titel'}</strong>
                  <span className={`asset-license ${licenseOk ? 'ok' : 'missing'}`}>
                    {licenseOk ? 'Lizenz ok' : 'Lizenz fehlt'}
                  </span>
                </div>
                <div className="asset-meta">
                  <span className="pill small">{ownerLabels[asset.owner_type]}</span>
                  <span className="pill small">{asset.kind}</span>
                  <span className="pill small">{formatDate(asset.created_at)}</span>
                </div>
                <div className="muted small mt12">
                  Quelle: {asset.source_name || asset.source_url || asset.source.toUpperCase()}
                </div>
                <div className="muted small">Lizenz: {asset.license_type || 'n/a'}</div>
                {asset.license_url && (
                  <a href={asset.license_url} className="muted small" target="_blank" rel="noreferrer">Lizenzlink</a>
                )}
                <div className="asset-stats">
                  <div>
                    <div className="muted small">Dimensionen</div>
                    <div>{summarizeDimension(asset)}</div>
                  </div>
                  <div>
                    <div className="muted small">Dateigröße</div>
                    <div>{formatBytes(asset.size_bytes)}</div>
                  </div>
                </div>
                <div className="asset-actions">
                  <button
                    className="btn ghost"
                    onClick={() => openOriginal(asset.id)}
                    disabled={downloadingId === asset.id}
                  >
                    {downloadingId === asset.id ? 'Lädt…' : 'Original'}
                  </button>
                  {asset.source_url && (
                    <a className="btn ghost" href={asset.source_url} target="_blank" rel="noreferrer">Quelle</a>
                  )}
                </div>
              </div>
            </div>
          )
        })}
        {!assets.length && !loading && (
          <EmptyState title="Keine Assets gefunden" message="Passe die Filter an oder entferne Suchbegriffe." />
        )}
      </div>

      <div className="row between mt12">
        <button className="btn" onClick={() => changePage('prev')} disabled={offset <= 0}>← Zurück</button>
        <span className="muted small">Offset {offset} · Limit {pageSize} · Ergebnisse {assets.length}</span>
        <button className="btn" onClick={() => changePage('next')} disabled={assets.length < pageSize}>Weiter →</button>
      </div>
    </div>
  )
}
