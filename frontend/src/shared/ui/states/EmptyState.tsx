import type { ReactNode } from 'react'

type EmptyStateProps = {
  title: string
  message?: string
  action?: ReactNode
}

export function EmptyState({ title, message, action }: EmptyStateProps) {
  return (
    <div className="empty-state card">
      <div className="title-strong">{title}</div>
      {message ? <div className="muted mt8">{message}</div> : null}
      {action ? <div className="mt12">{action}</div> : null}
    </div>
  )
}
