import { useI18n } from '../i18n/i18n'
import { useTheme } from './ThemeContext'

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 15.2A8.5 8.5 0 0 1 8.8 4a8.5 8.5 0 1 0 11.2 11.2Z" />
    </svg>
  )
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  )
}

export function ThemeToggle({ className = '' }: { className?: string }) {
  const { language } = useI18n()
  const { theme, toggleTheme } = useTheme()
  const isLight = theme === 'light'
  const label = isLight
    ? language === 'en'
      ? 'Switch to dark mode'
      : 'Zum Dark Mode wechseln'
    : language === 'en'
      ? 'Switch to light mode'
      : 'Zum hellen Modus wechseln'

  return (
    <button
      type="button"
      className={`theme-switch ${className}`.trim()}
      role="switch"
      aria-checked={isLight}
      aria-label={label}
      title={label}
      onClick={toggleTheme}
    >
      <span className="theme-switch-track" aria-hidden="true">
        <span className="theme-switch-icon theme-switch-moon">
          <MoonIcon />
        </span>
        <span className="theme-switch-icon theme-switch-sun">
          <SunIcon />
        </span>
        <span className="theme-switch-thumb" />
      </span>
    </button>
  )
}
