type InlineHintType = 'domain' | 'technical'

type InlineHintProps = {
  type: InlineHintType
  message: string
}

export function InlineHint({ type, message }: InlineHintProps) {
  return (
    <div className={`inline-hint ${type}`} role="status" aria-live="polite">
      <strong>{type === 'domain' ? 'Hinweis:' : 'Technischer Hinweis:'}</strong> {message}
    </div>
  )
}
