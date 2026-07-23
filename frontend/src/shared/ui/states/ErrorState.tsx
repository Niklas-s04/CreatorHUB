import { useI18n } from '../../i18n/i18n'

type ErrorStateProps = {
  title?: string
  message: string
  onRetry?: () => void
  retryLabel?: string
}

export function ErrorState({ title, message, onRetry, retryLabel }: ErrorStateProps) {
  const { t } = useI18n()

  return (
    <div className="error-state card state-card error" role="alert">
      <div className="title-strong">{title ?? t('common.loadError')}</div>
      <div className="error mt8">{message}</div>
      {onRetry ? (
        <div className="mt12">
          <button className="btn" onClick={onRetry}>
            {retryLabel || t('common.retry')}
          </button>
        </div>
      ) : null}
    </div>
  )
}
