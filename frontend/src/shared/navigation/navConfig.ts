import type { Permission } from '../../api'
import { type Language, translate } from '../i18n/i18n'

export type NavItem = {
  to: string
  label: string
  icon: string
  keywords: string[]
  requiredPermission?: Permission
}

export type NavSection = {
  title: string
  items: NavItem[]
}

export function buildNavSections(language: Language): NavSection[] {
  return [
    {
      title: translate(language, 'nav.sections.operations'),
      items: [
        {
          to: '/dashboard',
          label: translate(language, 'nav.dashboard'),
          icon: '◧',
          keywords: ['dashboard', 'übersicht', 'kpi', 'cockpit', 'overview', 'metrics'],
        },
        {
          to: '/operations',
          label: translate(language, 'nav.operationsInbox'),
          icon: '☰',
          keywords: [
            'operations',
            'inbox',
            'todo',
            'aufgaben',
            'freigaben',
            'eskalation',
            'tasks',
            'approvals',
          ],
        },
      ],
    },
    {
      title: translate(language, 'nav.sections.content'),
      items: [
        {
          to: '/projects',
          label: translate(language, 'nav.projects'),
          icon: '◆',
          keywords: ['projekte', 'projekt', 'briefing', 'kampagne', 'projects', 'campaign'],
        },
        {
          to: '/products',
          label: translate(language, 'nav.products'),
          icon: '◫',
          keywords: ['produkte', 'inventar', 'produkt', 'detail', 'products', 'inventory'],
        },
        {
          to: '/assets',
          label: translate(language, 'nav.assets'),
          icon: '◩',
          keywords: ['assets', 'mediathek', 'review', 'asset', 'media library'],
        },
        {
          to: '/content',
          label: translate(language, 'nav.contentPlan'),
          icon: '✎',
          keywords: ['content', 'kanban', 'aufgaben', 'planung', 'planning'],
        },
      ],
    },
    {
      title: translate(language, 'nav.sections.communication'),
      items: [
        {
          to: '/email',
          label: translate(language, 'nav.emailThreads'),
          icon: '✉',
          keywords: ['email', 'mail', 'kommunikation', 'deals', 'threads', 'correspondence'],
        },
      ],
    },
    {
      title: translate(language, 'nav.sections.governance'),
      items: [
        {
          to: '/admin',
          label: translate(language, 'nav.administration'),
          icon: '⌘',
          keywords: ['admin', 'registrierung', 'freigabe', 'user', 'approval'],
          requiredPermission: 'user.approve_registration',
        },
        {
          to: '/audit',
          label: translate(language, 'nav.audit'),
          icon: '⧉',
          keywords: ['audit', 'vorfälle', 'security', 'compliance', 'security review'],
          requiredPermission: 'audit.view',
        },
        {
          to: '/settings',
          label: translate(language, 'nav.settings'),
          icon: '⚙',
          keywords: ['settings', 'einstellungen', 'mfa', 'konto', 'account'],
        },
      ],
    },
  ]
}

export const NAV_SECTIONS_TASK_BASED = buildNavSections('de')

export function routeLabel(pathname: string, language: Language = 'de'): string {
  if (pathname === '/dashboard') return translate(language, 'breadcrumbs.dashboard')
  if (pathname === '/operations') return translate(language, 'nav.operationsInbox')
  if (pathname === '/products') return translate(language, 'nav.products')
  if (pathname === '/projects') return translate(language, 'nav.projects')
  if (pathname.startsWith('/products/')) return translate(language, 'breadcrumbs.productDetail')
  if (pathname === '/assets') return translate(language, 'nav.assets')
  if (pathname === '/content') return translate(language, 'nav.contentPlan')
  if (pathname === '/email') return translate(language, 'nav.emailThreads')
  if (pathname === '/admin') return translate(language, 'nav.administration')
  if (pathname === '/audit') return translate(language, 'nav.audit')
  if (pathname === '/settings') return translate(language, 'nav.settings')
  return translate(language, 'breadcrumbs.section')
}
