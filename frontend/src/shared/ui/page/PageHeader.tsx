import type { ReactNode } from 'react'

type PageHeaderProps = {
  title: string
  subtitle?: string
  right?: ReactNode
}

export function PageHeader({ title, subtitle, right }: PageHeaderProps) {
  return (
    <div className="page-header">
      <div>
        <h2 className="page-title">{title}</h2>
        {subtitle ? <div className="page-subtitle">{subtitle}</div> : null}
      </div>
      {right ? <div className="page-actions">{right}</div> : null}
    </div>
  )
}
