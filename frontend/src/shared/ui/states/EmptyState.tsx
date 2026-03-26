import type { ReactNode } from 'react'

type EmptyStateProps = {
  title: string
  message?: string
  action?: ReactNode
  live?: 'off' | 'polite'
}

export function EmptyState({ title, message, action, live = 'off' }: EmptyStateProps) {
  return (
    <div className="empty-state card state-card empty" role="status" aria-live={live} aria-atomic="true">
      <div className="title-strong">{title}</div>
      {message ? <div className="muted mt8">{message}</div> : null}
      {action ? <div className="mt12">{action}</div> : null}
    </div>
  )
}
