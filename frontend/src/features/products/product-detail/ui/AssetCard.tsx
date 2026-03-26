import { stripHtml } from '../../../../shared/lib/html'
import type { ProductAssetVm } from '../../../../shared/api/contracts'
import { useThumb } from './useThumb'

type AssetCardProps = {
  asset: ProductAssetVm
  canReview: boolean
  onReview: (id: number, state: 'approved' | 'rejected') => void
  onPrimary: (id: number) => void
}

export function AssetCard({ asset, canReview, onReview, onPrimary }: AssetCardProps) {
  const thumb = useThumb(String(asset.id))

  return (
    <div className="card tight">
      {thumb ? (
        <img
          src={thumb}
          className="img"
          loading="lazy"
          decoding="async"
          alt={asset.title || `Asset ${asset.id}`}
          width={320}
          height={180}
        />
      ) : (
        <div className="muted">No preview</div>
      )}

      <div className="asset-title">
        {asset.title || `asset ${asset.id}`}
      </div>

      <div className="muted small">
        {asset.source} • {asset.reviewState} {asset.isPrimary ? '• primary' : ''}
      </div>

      {(asset.licenseType || asset.attribution) && (
        <div className="muted small mt6">
          {asset.licenseType ? `Lizenz: ${asset.licenseType}` : ''}
          {asset.licenseType && asset.attribution ? ' • ' : ''}
          {asset.attribution ? `Attribution: ${stripHtml(asset.attribution)}` : ''}
        </div>
      )}

      {(asset.sourceUrl || asset.licenseUrl) && (
        <div className="muted small mt6">
          {asset.sourceUrl ? <a href={asset.sourceUrl} target="_blank" rel="noreferrer">Quelle</a> : null}
          {asset.sourceUrl && asset.licenseUrl ? ' • ' : null}
          {asset.licenseUrl ? <a href={asset.licenseUrl} target="_blank" rel="noreferrer">Lizenz</a> : null}
        </div>
      )}

      <div className="row mt10">
        <button className="btn" onClick={() => onPrimary(asset.id)} disabled={!canReview}>Primary</button>
        {canReview && asset.reviewState !== 'approved' && (
          <button className="btn primary" onClick={() => onReview(asset.id, 'approved')}>Approve</button>
        )}
        {canReview && asset.reviewState !== 'rejected' && (
          <button className="btn danger" onClick={() => onReview(asset.id, 'rejected')}>Reject</button>
        )}
      </div>
    </div>
  )
}
