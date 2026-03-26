type InlineHintType = 'domain' | 'technical' | 'success' | 'warning' | 'error'

type InlineHintProps = {
  type: InlineHintType
  message: string
}

export function InlineHint({ type, message }: InlineHintProps) {
  const label = type === 'domain' || type === 'success'
    ? 'Hinweis:'
    : type === 'warning'
      ? 'Warnung:'
      : 'Technischer Hinweis:'

  return (
    <div className={`inline-hint ${type}`} role="status" aria-live="polite">
      <strong>{label}</strong> {message}
    </div>
  )
}
