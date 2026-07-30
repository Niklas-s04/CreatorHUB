import { NavLink } from 'react-router'
import { logout } from '../../../api'
import { useAuthz } from '../../hooks/useAuthz'
import { useI18n } from '../../i18n/i18n'
import { buildNavSections } from '../../navigation/navConfig'
import { AppLogo } from '../brand/AppLogo'

export default function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { hasPermission } = useAuthz()
  const { language, t } = useI18n()
  const sections = buildNavSections(language)

  async function onLogout() {
    try {
      await logout()
    } finally {
      window.location.href = '/login'
    }
  }

  return (
    <aside className="sidebar" aria-label={t('common.sidebarNavigation')}>
      <div className="sidebar-brand">
        <AppLogo />
      </div>
      <nav className="sidebar-nav" aria-label={t('common.mainNavigation')}>
        {sections.map((section) => (
          <section className="sidebar-section" key={section.title} aria-label={section.title}>
            <div className="sidebar-section-title">{section.title}</div>
            {section.items
              .filter((item) => !item.requiredPermission || hasPermission(item.requiredPermission))
              .map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/dashboard'}
                  className={({ isActive }) => (isActive ? 'sidebar-link active' : 'sidebar-link')}
                  onClick={onNavigate}
                >
                  <span className="sidebar-icon" aria-hidden="true">
                    {item.icon}
                  </span>
                  <span>{item.label}</span>
                </NavLink>
              ))}
          </section>
        ))}
      </nav>
      <button type="button" className="sidebar-logout" onClick={onLogout}>
        <span className="sidebar-icon" aria-hidden="true">
          ⇥
        </span>
        <span>{t('common.logout')}</span>
      </button>
    </aside>
  )
}
