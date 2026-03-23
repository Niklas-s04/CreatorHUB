type GlobalLoadingProps = {
  label?: string
}

export function GlobalLoading({ label = 'Lade Anwendung…' }: GlobalLoadingProps) {
  return (
    <div className="global-loading" role="status" aria-live="polite" aria-label={label}>
      <div className="global-loading-card">
        <span className="spinner" aria-hidden="true" />
        <span>{label}</span>
      </div>
    </div>
  )
}
