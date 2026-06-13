import { useI18n } from '../../i18n/i18n'

type GlobalLoadingProps = {
  label?: string
}

export function GlobalLoading({ label }: GlobalLoadingProps) {
  const { t } = useI18n()
  const resolvedLabel = label || t('app.loadingApplication')

  return (
    <div className="global-loading" role="status" aria-live="polite" aria-label={resolvedLabel}>
      <div className="global-loading-card">
        <span className="spinner" aria-hidden="true" />
        <span>{resolvedLabel}</span>
      </div>
    </div>
  )
}
