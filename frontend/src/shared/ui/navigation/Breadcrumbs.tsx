import { Link, useLocation } from 'react-router-dom'
import { useI18n } from '../../i18n/i18n'
import { routeLabel } from '../../navigation/navConfig'

type Crumb = {
  label: string
  to?: string
}

function buildCrumbs(pathname: string, language: 'de' | 'en'): Crumb[] {
  const crumbs: Crumb[] = [{ label: routeLabel('/dashboard', language), to: '/dashboard' }]

  if (pathname === '/dashboard') {
    return [{ label: routeLabel('/dashboard', language) }]
  }

  const segments = pathname.split('/').filter(Boolean)
  if (!segments.length) return [{ label: routeLabel('/dashboard', language) }]

  let currentPath = ''
  for (let i = 0; i < segments.length; i++) {
    currentPath += `/${segments[i]}`
    const isLast = i === segments.length - 1

    let label = routeLabel(currentPath, language)
    if (segments[0] === 'products' && i === 1) {
      label = `${routeLabel('/products', language)} ${segments[i]}`
    } else if (label === 'Bereich') {
      label = decodeURIComponent(segments[i])
    }

    crumbs.push({
      label,
      to: isLast ? undefined : currentPath,
    })
  }

  return crumbs
}

export function Breadcrumbs() {
  const location = useLocation()
  const { language } = useI18n()
  const crumbs = buildCrumbs(location.pathname, language)

  return (
    <nav className="breadcrumbs" aria-label="Breadcrumb">
      {crumbs.map((crumb, index) => (
        <span key={`${crumb.label}-${index}`} className="breadcrumb-item">
          {crumb.to ? <Link to={crumb.to}>{crumb.label}</Link> : <span>{crumb.label}</span>}
          {index < crumbs.length - 1 ? <span className="breadcrumb-sep">/</span> : null}
        </span>
      ))}
    </nav>
  )
}
