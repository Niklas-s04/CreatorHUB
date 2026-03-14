import React, { useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch, apiFetchBlob } from '../api'

type AssetOwnerType = 'product' | 'content' | 'email' | 'deal'
type AssetKind = 'image' | 'pdf' | 'link' | 'video'
type AssetReviewState = 'pending' | 'approved' | 'rejected'
type LicenseFilter = 'any' | 'licensed' | 'missing'

type Asset = {
  id: string
  owner_type: AssetOwnerType
  owner_id: string
  kind: AssetKind
  source: 'upload' | 'web'
  title: string | null
  license_type: string | null
  license_url: string | null
  license_state?: string | null
  attribution: string | null
  source_name: string | null
  source_url: string | null
  review_state: AssetReviewState
  is_primary: boolean
  url: string | null
  width: number | null
  height: number | null
  size_bytes: number | null
  created_at: string
  updated_at: string
}

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

function summarizeDimension(asset: Asset) {
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

function hasLicense(asset: Asset) {
  return Boolean(asset.license_type || asset.license_url)
}

export default function AssetsPage() {
  const [searchInput, setSearchInput] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [ownerType, setOwnerType] = useState<'' | AssetOwnerType>('')
  const [kind, setKind] = useState<'' | AssetKind>('')
  const [approvedOnly, setApprovedOnly] = useState(true)
  const [primaryOnly, setPrimaryOnly] = useState(false)
  const [licenseFilter, setLicenseFilter] = useState<LicenseFilter>('any')
  const [assets, setAssets] = useState<Asset[]>([])
  const [thumbs, setThumbs] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [refreshIndex, setRefreshIndex] = useState(0)
  const [downloadingId, setDownloadingId] = useState<string | null>(null)
  const thumbCacheRef = useRef<Record<string, string>>({})

  useEffect(() => {
    return () => {
      Object.values(thumbCacheRef.current).forEach(url => URL.revokeObjectURL(url))
    }
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => setSearchTerm(searchInput.trim()), 400)
    return () => clearTimeout(timer)
  }, [searchInput])

  useEffect(() => {
    let cancelled = false
    async function fetchAssets() {
      setLoading(true)
      setErr(null)
      try {
        const params = new URLSearchParams()
        if (searchTerm) params.set('search', searchTerm)
        if (ownerType) params.set('owner_type', ownerType)
        if (kind) params.set('kind', kind)
        params.set('primary_only', primaryOnly ? 'true' : 'false')
        params.set('approved_only', approvedOnly ? 'true' : 'false')
        params.set('license_filter', licenseFilter)
        params.set('limit', '120')
        const qs = params.toString()
        const data = await apiFetch(`/assets/library${qs ? `?${qs}` : ''}`) as Asset[]
        if (!cancelled) {
          Object.values(thumbCacheRef.current).forEach(url => URL.revokeObjectURL(url))
          thumbCacheRef.current = {}
          setThumbs({})
          setAssets(data)
        }
      } catch (e: any) {
        if (!cancelled) setErr(e.message || String(e))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    fetchAssets()
    return () => { cancelled = true }
  }, [searchTerm, ownerType, kind, approvedOnly, primaryOnly, licenseFilter, refreshIndex])

  useEffect(() => {
    const images = assets.filter(a => a.kind === 'image')
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
  }, [assets])

  const stats = useMemo(() => {
    const licensed = assets.filter(a => hasLicense(a)).length
    const primary = assets.filter(a => a.is_primary).length
    return { licensed, missing: Math.max(0, assets.length - licensed), primary }
  }, [assets])

  function reload() {
    setRefreshIndex(v => v + 1)
  }

  async function openOriginal(assetId: string) {
    setDownloadingId(assetId)
    try {
      const blob = await apiFetchBlob(`/assets/${assetId}/file`)
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank', 'noopener')
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch (e: any) {
      setErr(`Download fehlgeschlagen: ${e.message || String(e)}`)
    } finally {
      setDownloadingId(curr => (curr === assetId ? null : curr))
    }
  }

  return (
    <div className="container pt60">
      <div className="row between">
        <div>
          <h2>Mediathek</h2>
          <div className="muted">Suche, filtere und exportiere geprüfte Assets.</div>
        </div>
        <div className="row" style={{ gap: 12 }}>
          <div className="card tight">
            <div className="muted small">Gefiltert</div>
            <div className="kpi">{assets.length}</div>
          </div>
          <div className="card tight">
            <div className="muted small">Lizenz ok</div>
            <div className="kpi" style={{ fontSize: 24 }}>{stats.licensed}</div>
          </div>
          <div className="card tight">
            <div className="muted small">Primary</div>
            <div className="kpi" style={{ fontSize: 24 }}>{stats.primary}</div>
          </div>
        </div>
      </div>

      {err && <div className="error mt12">{err}</div>}

      <div className="card asset-controls mt16">
        <div className="row" style={{ alignItems: 'stretch' }}>
          <input
            className="grow"
            placeholder="Suche (Titel, Quelle, URL)"
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
          />
          <button className="btn" onClick={reload} disabled={loading}>Refresh</button>
        </div>
        <div className="row" style={{ flexWrap: 'wrap' }}>
          <select value={ownerType} onChange={e => setOwnerType(e.target.value as AssetOwnerType | '')}>
            {ownerTypeOptions.map(opt => (
              <option key={opt.value || 'all'} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <select value={kind} onChange={e => setKind(e.target.value as AssetKind | '')}>
            {kindOptions.map(opt => (
              <option key={opt.value || 'all'} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <select value={licenseFilter} onChange={e => setLicenseFilter(e.target.value as LicenseFilter)}>
            {licenseFilterOptions.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
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

      {loading && <div className="muted small mt12">Lade Assets…</div>}

      <div className="asset-grid mt16">
        {assets.map(asset => {
          const thumbUrl = thumbs[asset.id]
          const licenseOk = hasLicense(asset)
          return (
            <div key={asset.id} className="asset-card">
              <div className="asset-cover">
                {asset.kind === 'image' && thumbUrl && (
                  <img src={thumbUrl} alt={asset.title || 'Asset preview'} />
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
                <div className="row between" style={{ alignItems: 'flex-start' }}>
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
          <div className="card" style={{ gridColumn: '1 / -1' }}>
            <div className="muted">Keine Assets gefunden. Filter anpassen.</div>
          </div>
        )}
      </div>
    </div>
  )
}
