import type { Permission } from '../../api'

export type NavItem = {
  to: string
  label: string
  icon: string
  keywords: string[]
  requiredPermission?: Permission
}

export type NavSection = {
  title: 'Operations' | 'Content' | 'Communication' | 'Governance'
  items: NavItem[]
}

export const NAV_SECTIONS_TASK_BASED: NavSection[] = [
  {
    title: 'Operations',
    items: [
      {
        to: '/dashboard',
        label: 'Dashboard',
        icon: '◧',
        keywords: ['dashboard', 'übersicht', 'kpi', 'cockpit'],
      },
      {
        to: '/operations',
        label: 'Operations Inbox',
        icon: '☰',
        keywords: ['operations', 'inbox', 'todo', 'aufgaben', 'freigaben', 'eskalation'],
      },
    ],
  },
  {
    title: 'Content',
    items: [
      {
        to: '/products',
        label: 'Produkte',
        icon: '◫',
        keywords: ['produkte', 'inventar', 'produkt', 'detail'],
      },
      {
        to: '/assets',
        label: 'Assets',
        icon: '◩',
        keywords: ['assets', 'mediathek', 'review', 'asset'],
      },
      {
        to: '/content',
        label: 'Content Plan',
        icon: '✎',
        keywords: ['content', 'kanban', 'aufgaben', 'planung'],
      },
    ],
  },
  {
    title: 'Communication',
    items: [
      {
        to: '/email',
        label: 'E-Mail Threads',
        icon: '✉',
        keywords: ['email', 'mail', 'kommunikation', 'deals', 'threads'],
      },
    ],
  },
  {
    title: 'Governance',
    items: [
      {
        to: '/admin',
        label: 'Administration',
        icon: '⌘',
        keywords: ['admin', 'registrierung', 'freigabe', 'user'],
        requiredPermission: 'user.approve_registration',
      },
      {
        to: '/audit',
        label: 'Audit',
        icon: '⧉',
        keywords: ['audit', 'vorfälle', 'security', 'compliance'],
        requiredPermission: 'audit.view',
      },
      {
        to: '/settings',
        label: 'Einstellungen',
        icon: '⚙',
        keywords: ['settings', 'einstellungen', 'mfa', 'konto'],
      },
    ],
  },
]

export function routeLabel(pathname: string): string {
  if (pathname === '/dashboard') return 'Dashboard'
  if (pathname === '/operations') return 'Operations Inbox'
  if (pathname === '/products') return 'Produkte'
  if (pathname.startsWith('/products/')) return 'Produktdetail'
  if (pathname === '/assets') return 'Assets'
  if (pathname === '/content') return 'Content Plan'
  if (pathname === '/email') return 'E-Mail Threads'
  if (pathname === '/admin') return 'Administration'
  if (pathname === '/audit') return 'Audit'
  if (pathname === '/settings') return 'Einstellungen'
  return 'Bereich'
}
