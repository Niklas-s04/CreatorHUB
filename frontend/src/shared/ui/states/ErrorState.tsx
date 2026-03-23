type ErrorStateProps = {
  title?: string
  message: string
  onRetry?: () => void
  retryLabel?: string
}

export function ErrorState({
  title = 'Fehler beim Laden',
  message,
  onRetry,
  retryLabel = 'Erneut versuchen',
}: ErrorStateProps) {
  return (
    <div className="error-state card" role="alert">
      <div className="title-strong">{title}</div>
      <div className="error mt8">{message}</div>
      {onRetry ? (
        <div className="mt12">
          <button className="btn" onClick={onRetry}>{retryLabel}</button>
        </div>
      ) : null}
    </div>
  )
}
