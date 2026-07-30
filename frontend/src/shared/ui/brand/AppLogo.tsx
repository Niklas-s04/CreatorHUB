import logoUrl from '../../../assets/logo.webp'
import { useI18n } from '../../i18n/i18n'

type AppLogoProps = {
  compact?: boolean
}

export function AppLogo({ compact = false }: AppLogoProps) {
  const { t } = useI18n()

  return (
    <span className={compact ? 'app-logo compact' : 'app-logo'}>
      <img src={logoUrl} alt="" aria-hidden="true" />
      {!compact && <span>{t('app.appName')}</span>}
    </span>
  )
}
