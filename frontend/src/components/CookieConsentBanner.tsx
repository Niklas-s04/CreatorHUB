import { useEffect, useState } from 'react'
import { useI18n } from '../shared/i18n/i18n'

type ConsentLevel = 'necessary' | 'all'

const STORAGE_KEY = 'consent_level'

function readConsentLevel(): ConsentLevel | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    if (value === 'necessary' || value === 'all') return value
  } catch {
    return null
  }
  return null
}

function persistConsentLevel(level: ConsentLevel) {
  window.localStorage.setItem(STORAGE_KEY, level)
  window.dispatchEvent(new CustomEvent('creatorhub:consent-change', { detail: { level } }))
}

export default function CookieConsentBanner() {
  const [visible, setVisible] = useState(false)
  const { t } = useI18n()

  useEffect(() => {
    setVisible(readConsentLevel() === null)
  }, [])

  if (!visible) return null

  function acceptNecessaryOnly() {
    persistConsentLevel('necessary')
    setVisible(false)
  }

  function acceptAll() {
    persistConsentLevel('all')
    setVisible(false)
  }

  return (
    <section className="cookie-consent" role="region" aria-labelledby="cookie-consent-title">
      <div className="cookie-consent__copy">
        <p className="cookie-consent__eyebrow">{t('cookie.eyebrow')}</p>
        <h2 id="cookie-consent-title">{t('cookie.title')}</h2>
        <p>{t('cookie.body')}</p>
      </div>
      <div className="cookie-consent__actions">
        <button type="button" className="btn secondary" onClick={acceptNecessaryOnly}>
          {t('cookie.necessaryOnly')}
        </button>
        <button type="button" className="btn primary" onClick={acceptAll}>
          {t('cookie.allowAnalytics')}
        </button>
      </div>
    </section>
  )
}
