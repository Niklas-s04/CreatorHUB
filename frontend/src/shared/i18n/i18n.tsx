import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type Language = 'de' | 'en'

const STORAGE_KEY = 'creatorhub.ui_language'
const LANGUAGE_CHANGE_EVENT = 'creatorhub:language-change'

const translations = {
  de: {
    app: {
      loadingSession: 'Session wird geprüft…',
      loadingPage: 'Seite wird geladen…',
      loadingApplication: 'Lade Anwendung…',
      menuOpen: 'Navigation öffnen',
      menuClose: 'Navigation schließen',
      appName: 'CreatorHUB',
    },
    common: {
      retry: 'Erneut versuchen',
      refresh: 'Aktualisieren',
      open: 'Öffnen',
      save: 'Speichern',
      cancel: 'Abbrechen',
      logout: 'Logout',
      language: 'Sprache',
      german: 'Deutsch',
      english: 'Englisch',
      search: 'Globale Suche',
      searchPlaceholder: 'Global suchen: Produkte, Assets, Content, Knowledge, Benutzer …',
      notAvailable: 'Nicht verfügbar',
      yes: 'Ja',
      no: 'Nein',
      loadError: 'Fehler beim Laden',
      sidebarNavigation: 'Seitennavigation',
      mainNavigation: 'Hauptnavigation',
    },
    cookie: {
      eyebrow: 'Privacy and cookies',
      title: 'Notwendige Cookies sind erforderlich',
      body: 'Wir verwenden erforderliche Cookies für Authentifizierung und CSRF-Schutz. Optionale Analytics oder Telemetrie werden nur mit deiner Zustimmung aktiviert.',
      necessaryOnly: 'Nur notwendige Cookies',
      allowAnalytics: 'Analytics erlauben',
    },
    nav: {
      sections: {
        operations: 'Operations',
        content: 'Content',
        communication: 'Communication',
        governance: 'Governance',
      },
      dashboard: 'Dashboard',
      operationsInbox: 'Operations Inbox',
      products: 'Produkte',
      assets: 'Assets',
      contentPlan: 'Content Plan',
      emailThreads: 'E-Mail Threads',
      administration: 'Administration',
      audit: 'Audit',
      settings: 'Einstellungen',
    },
    breadcrumbs: {
      dashboard: 'Dashboard',
      productDetail: 'Produktdetail',
      section: 'Bereich',
    },
    login: {
      title: 'Login',
      brandSubline: 'CreatorHUB',
      heroTitle: 'Creator Operations an einem sicheren Ort.',
      heroCopy: 'Ein ruhiger Einstieg fuer Admins, Redaktion und Operations.',
      welcomeBack: 'Willkommen zurueck',
      setupTitle: 'Admin einrichten',
      authMode: 'Login-Modus',
      modeLogin: 'Login',
      modeRegister: 'Registrieren',
      modeReset: 'Passwort-Reset',
      firstSetup: 'Erstsetup',
      closeSetup: 'Erstsetup ausblenden',
      bootstrapTokenLabel: 'Bootstrap-Token (nur Erstsetup)',
      bootstrapTokenPlaceholder: 'Install-Token',
      checkBootstrap: 'Erstsetup prüfen',
      setupHint: 'Erststart: Admin-Passwort für Benutzer {adminUsername} setzen.',
      registerHint: 'Bei Registrierung wird eine Anfrage an den Admin gestellt.',
      loginHint: 'Melde dich mit deinem Benutzerkonto an.',
      resetHint: 'Fordere einen Reset an oder bestaetige einen vorhandenen Reset-Token.',
      username: 'Username',
      password: 'Password',
      passwordRepeat: 'Password wiederholen',
      showPassword: 'Passwort anzeigen',
      hidePassword: 'Passwort verbergen',
      otp: 'MFA-Code (optional)',
      otpPlaceholder: 'TOTP oder Recovery-Code',
      resetToken: 'Reset-Token (optional für Bestätigung)',
      resetTokenPlaceholder: 'Token einfügen, um neues Passwort zu setzen',
      submitLogin: 'Login',
      submitSetup: 'Admin-Passwort setzen',
      submitRegister: 'Anfrage senden',
      submitResetRequest: 'Reset anfordern',
      submitResetConfirm: 'Passwort setzen',
      loginSuccess: 'Login erfolgreich',
      adminPasswordSet: 'Admin-Passwort wurde gesetzt',
      registrationRequested: 'Registrierungsanfrage gesendet',
      resetRequested: 'Passwort-Reset angefordert',
      passwordResetComplete: 'Passwort wurde zurückgesetzt',
      passwordResetCompleteHint: 'Passwort wurde zurückgesetzt. Bitte einloggen.',
      bootstrapMissing: 'Bootstrap-Token erforderlich',
      bootstrapAlreadyDone: 'Erstsetup bereits abgeschlossen.',
      bootstrapReady: 'Erstsetup freigeschaltet.',
      bootstrapReadyToast: 'Erstsetup freigeschaltet',
      resetTokenLabel: 'Reset-Token: {token}',
      resetFallback: 'Falls der Benutzer existiert, wurde ein Reset ausgelöst.',
      adminSetupHint: 'Beim Erstsetup das Admin-Passwort für Benutzer {adminUsername} setzen.',
      registerInfo: 'Bei Registrierung wird eine Anfrage an den Admin gestellt.',
    },
    dashboard: {
      title: 'Operatives Dashboard',
      roleAdmin: 'Admin-Fokus: Governance, Freigaben und Security',
      roleEditor: 'Editor-Fokus: Delivery, offene Freigaben und Risiken',
      roleViewer: 'Viewer-Fokus: Transparenz über operative Blocker',
      roleFallback: 'Rollenfokus: {role}',
      loadError: 'Dashboard konnte nicht geladen werden',
      noMetricsTitle: 'Keine operativen KPIs verfügbar',
      noMetricsBody: 'Für deine Rolle stehen aktuell keine Dashboard-Kennzahlen zur Verfügung.',
      noItems: 'Keine offenen Einträge.',
      openWorklist: 'Zur Arbeitsliste',
      open: 'Öffnen',
    },
    contentHub: {
      title: 'Content Hub',
      subtitle: 'Videos mit Plattformfeldern, Vorlagen und Checklisten planen und managen.',
      newVideoTitlePlaceholder: 'Video-Titel...',
      addVideo: '+ Video anlegen',
      tabsAriaLabel: 'Content-Hub Tabs',
      tabs: {
        board: 'Plan',
        calendar: 'Kalender',
        checklist: 'Checkliste',
        templates: 'Vorlagen',
      },
      selectItem: 'Wähle ein Item aus.',
      selectItemForPlanning: 'Wähle ein Item für den Planungsstatus.',
      untitled: 'Ohne Titel',
      delete: 'Löschen',
      tasksTitle: 'Tasks',
      taskFallback: 'Task',
      noPlannedContent: 'Kein geplanter Content.',
      readiness: 'Readiness',
      publishReady: 'Publish ready',
      apply: 'Anwenden',
      createTemplate: 'Vorlage erstellen',
      templateNamePlaceholder: 'Vorlagenname',
      firstChecklistItemPlaceholder: 'Erster Checklistenpunkt',
      templateItemsCount: '{count} items',
      noTemplates: 'Keine Vorlagen.',
      newTaskPlaceholder: 'Neue Task...',
      add: '+ Hinzufügen',
      status: {
        idea: 'Idee',
        draft: 'Entwurf',
        recorded: 'Aufgenommen',
        edited: 'Geschnitten',
        scheduled: 'Geplant',
        published: 'Veröffentlicht',
      },
      taskStatus: {
        todo: 'Offen',
        doing: 'In Arbeit',
        done: 'Fertig',
      },
      all: 'Alle',
    },
    settings: {
      title: 'Einstellungen',
      subtitle: 'Brand Voice / Policy / Templates für den E-Mail-Assistenten.',
      loadError: 'Einstellungen konnten nicht geladen werden',
      accountSecurity: 'Account-Sicherheit',
      mfaActive: 'Aktiv',
      mfaInactive: 'Inaktiv',
      currentPassword: 'Aktuelles Passwort',
      newPassword: 'Neues Passwort',
      totpCode: 'TOTP-Code',
      mfaPassword: 'Passwort für MFA-Deaktivierung',
      mfaDisableCode: 'TOTP oder Recovery-Code für MFA-Deaktivierung',
      confirmation: 'Bestätigung',
      appLanguageCardTitle: 'App-Sprache',
      appLanguageCardBody:
        'Wähle die Sprache für Navigation, Buttons und Systemtexte der Oberfläche.',
      appLanguageLabel: 'Sprache der App',
      languageDescription: 'Die Auswahl wird lokal gespeichert und sofort übernommen.',
      languageGerman: 'Deutsch',
      languageEnglish: 'Englisch',
      saveProfile: 'Profil speichern',
      savingProfile: 'Speichere…',
      activeSettingsSource: 'Aktive Settings-Quelle',
      profile: 'Profil',
      missingRequired: 'Fehlende Pflichtfelder (Fallback aktiv)',
      fallback: 'Fallback',
      documentSaved: 'Dokument gespeichert',
      passwordChanged: 'Passwort erfolgreich geändert',
      totpCreated: 'TOTP-Secret wurde erzeugt',
      mfaEnabled: 'MFA wurde aktiviert',
      mfaDisabled: 'MFA wurde deaktiviert',
      sessionEnded: 'Session beendet',
      knowledgeSubtitle: 'Wissensdokumente für den Assistenten',
      languageShortHint: 'de oder en',
    },
  },
  en: {
    app: {
      loadingSession: 'Checking session…',
      loadingPage: 'Loading page…',
      loadingApplication: 'Loading application…',
      menuOpen: 'Open menu',
      menuClose: 'Close menu',
      appName: 'CreatorHUB',
    },
    common: {
      retry: 'Retry',
      refresh: 'Refresh',
      open: 'Open',
      save: 'Save',
      cancel: 'Cancel',
      logout: 'Logout',
      language: 'Language',
      german: 'German',
      english: 'English',
      search: 'Global search',
      searchPlaceholder: 'Search globally: products, assets, content, knowledge, users …',
      notAvailable: 'Not available',
      yes: 'Yes',
      no: 'No',
      loadError: 'Load error',
      sidebarNavigation: 'Side navigation',
      mainNavigation: 'Main navigation',
    },
    cookie: {
      eyebrow: 'Privacy and cookies',
      title: 'Necessary cookies are required',
      body: 'We use required cookies for authentication and CSRF protection. Optional analytics or telemetry can only be enabled with your consent.',
      necessaryOnly: 'Necessary only',
      allowAnalytics: 'Allow analytics',
    },
    nav: {
      sections: {
        operations: 'Operations',
        content: 'Content',
        communication: 'Communication',
        governance: 'Governance',
      },
      dashboard: 'Dashboard',
      operationsInbox: 'Operations Inbox',
      products: 'Products',
      assets: 'Assets',
      contentPlan: 'Content Plan',
      emailThreads: 'Email Threads',
      administration: 'Administration',
      audit: 'Audit',
      settings: 'Settings',
    },
    breadcrumbs: {
      dashboard: 'Dashboard',
      productDetail: 'Product detail',
      section: 'Section',
    },
    login: {
      title: 'Login',
      brandSubline: 'CreatorHUB',
      heroTitle: 'Creator operations in one secure place.',
      heroCopy: 'A calm entry point for admins, editorial teams, and operations.',
      welcomeBack: 'Welcome back',
      setupTitle: 'Set up admin',
      authMode: 'Login mode',
      modeLogin: 'Login',
      modeRegister: 'Register',
      modeReset: 'Password reset',
      firstSetup: 'First setup',
      closeSetup: 'Hide first setup',
      bootstrapTokenLabel: 'Bootstrap token (first setup only)',
      bootstrapTokenPlaceholder: 'Install token',
      checkBootstrap: 'Check first setup',
      setupHint: 'First start: set the admin password for user {adminUsername}.',
      registerHint: 'Registration sends a request to the admin.',
      loginHint: 'Sign in with your user account.',
      resetHint: 'Request a reset or confirm an existing reset token.',
      username: 'Username',
      password: 'Password',
      passwordRepeat: 'Repeat password',
      showPassword: 'Show password',
      hidePassword: 'Hide password',
      otp: 'MFA code (optional)',
      otpPlaceholder: 'TOTP or recovery code',
      resetToken: 'Reset token (optional for confirmation)',
      resetTokenPlaceholder: 'Paste token to set a new password',
      submitLogin: 'Login',
      submitSetup: 'Set admin password',
      submitRegister: 'Send request',
      submitResetRequest: 'Request reset',
      submitResetConfirm: 'Set password',
      loginSuccess: 'Login successful',
      adminPasswordSet: 'Admin password was set',
      registrationRequested: 'Registration request sent',
      resetRequested: 'Password reset requested',
      passwordResetComplete: 'Password was reset',
      passwordResetCompleteHint: 'Password was reset. Please sign in.',
      bootstrapMissing: 'Bootstrap token required',
      bootstrapAlreadyDone: 'First setup is already complete.',
      bootstrapReady: 'First setup unlocked.',
      bootstrapReadyToast: 'First setup unlocked',
      resetTokenLabel: 'Reset token: {token}',
      resetFallback: 'If the user exists, a reset was triggered.',
      adminSetupHint: 'During first setup, set the admin password for user {adminUsername}.',
      registerInfo: 'Registration sends a request to the admin.',
    },
    dashboard: {
      title: 'Operational dashboard',
      roleAdmin: 'Admin focus: governance, approvals and security',
      roleEditor: 'Editor focus: delivery, open approvals and risks',
      roleViewer: 'Viewer focus: transparency about operational blockers',
      roleFallback: 'Role focus: {role}',
      loadError: 'Dashboard could not be loaded',
      noMetricsTitle: 'No operational KPIs available',
      noMetricsBody: 'There are currently no dashboard metrics for your role.',
      noItems: 'No open items.',
      openWorklist: 'Open worklist',
      open: 'Open',
    },
    contentHub: {
      title: 'Content Hub',
      subtitle: 'Plan and manage videos with platform fields, templates and checklists.',
      newVideoTitlePlaceholder: 'Video title...',
      addVideo: '+ Add video',
      tabsAriaLabel: 'Content hub tabs',
      tabs: {
        board: 'Plan',
        calendar: 'Calendar',
        checklist: 'Checklist',
        templates: 'Templates',
      },
      selectItem: 'Select an item.',
      selectItemForPlanning: 'Select an item to inspect planning state.',
      untitled: 'Untitled',
      delete: 'Delete',
      tasksTitle: 'Tasks',
      taskFallback: 'Task',
      noPlannedContent: 'No planned content.',
      readiness: 'Readiness',
      publishReady: 'Publish ready',
      apply: 'Apply',
      createTemplate: 'Create template',
      templateNamePlaceholder: 'Template name',
      firstChecklistItemPlaceholder: 'First checklist item',
      templateItemsCount: '{count} items',
      noTemplates: 'No templates.',
      newTaskPlaceholder: 'New task...',
      add: '+ Add',
      status: {
        idea: 'Idea',
        draft: 'Draft',
        recorded: 'Recorded',
        edited: 'Edited',
        scheduled: 'Scheduled',
        published: 'Published',
      },
      taskStatus: {
        todo: 'Todo',
        doing: 'Doing',
        done: 'Done',
      },
      all: 'All',
    },
    settings: {
      title: 'Settings',
      subtitle: 'Brand voice / policy / templates for the email assistant.',
      loadError: 'Settings could not be loaded',
      accountSecurity: 'Account security',
      mfaActive: 'Active',
      mfaInactive: 'Inactive',
      currentPassword: 'Current password',
      newPassword: 'New password',
      totpCode: 'TOTP code',
      mfaPassword: 'Password for MFA disable',
      mfaDisableCode: 'TOTP or recovery code for MFA disable',
      confirmation: 'Confirmation',
      appLanguageCardTitle: 'App language',
      appLanguageCardBody:
        'Choose the language for navigation, buttons, and system text in the interface.',
      appLanguageLabel: 'App language',
      languageDescription: 'The choice is stored locally and applied immediately.',
      languageGerman: 'German',
      languageEnglish: 'English',
      saveProfile: 'Save profile',
      savingProfile: 'Saving…',
      activeSettingsSource: 'Active settings source',
      profile: 'Profile',
      missingRequired: 'Missing required fields (fallback active)',
      fallback: 'Fallback',
      documentSaved: 'Document saved',
      passwordChanged: 'Password changed successfully',
      totpCreated: 'TOTP secret created',
      mfaEnabled: 'MFA was enabled',
      mfaDisabled: 'MFA was disabled',
      sessionEnded: 'Session ended',
      knowledgeSubtitle: 'Knowledge documents for the assistant',
      languageShortHint: 'de or en',
    },
  },
} as const

export type TranslationKey = string

function hasWindow(): boolean {
  return typeof window !== 'undefined'
}

export function getStoredLanguage(): Language {
  if (!hasWindow()) return 'de'
  try {
    const value = window.localStorage.getItem(STORAGE_KEY)
    if (value === 'de' || value === 'en') return value
  } catch {
    return 'de'
  }
  return 'de'
}

export function setStoredLanguage(language: Language) {
  if (!hasWindow()) return
  window.localStorage.setItem(STORAGE_KEY, language)
  window.document.documentElement.lang = language
  window.dispatchEvent(new CustomEvent(LANGUAGE_CHANGE_EVENT, { detail: { language } }))
}

function getValue(language: Language, key: string): unknown {
  const parts = key.split('.')
  let current: unknown = translations[language]
  for (const part of parts) {
    if (!current || typeof current !== 'object') return undefined
    current = (current as Record<string, unknown>)[part]
  }
  return current
}

export function translate(
  language: Language,
  key: string,
  params?: Record<string, string | number>
): string {
  const candidate = getValue(language, key) ?? getValue('de', key)
  if (typeof candidate !== 'string') return key
  if (!params) return candidate
  return candidate.replace(/\{([^}]+)\}/g, (_, paramKey: string) => {
    const value = params[paramKey]
    return value === undefined ? `{${paramKey}}` : String(value)
  })
}

type I18nContextValue = {
  language: Language
  setLanguage: (language: Language) => void
  t: (key: string, params?: Record<string, string | number>) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() => getStoredLanguage())

  useEffect(() => {
    if (!hasWindow()) return
    window.document.documentElement.lang = language
  }, [language])

  useEffect(() => {
    if (!hasWindow()) return

    function onLanguageChange(event: Event) {
      const custom = event as CustomEvent<{ language?: string }>
      if (custom.detail?.language === 'de' || custom.detail?.language === 'en') {
        setLanguageState(custom.detail.language)
      }
    }

    function onStorage(event: StorageEvent) {
      if (event.key !== STORAGE_KEY) return
      if (event.newValue === 'de' || event.newValue === 'en') {
        setLanguageState(event.newValue)
      }
    }

    window.addEventListener(LANGUAGE_CHANGE_EVENT, onLanguageChange as EventListener)
    window.addEventListener('storage', onStorage)
    return () => {
      window.removeEventListener(LANGUAGE_CHANGE_EVENT, onLanguageChange as EventListener)
      window.removeEventListener('storage', onStorage)
    }
  }, [])

  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      setLanguage: (next) => {
        setLanguageState(next)
        setStoredLanguage(next)
      },
      t: (key, params) => translate(language, key, params),
    }),
    [language]
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (context) return context

  const language = getStoredLanguage()
  return {
    language,
    setLanguage: setStoredLanguage,
    t: (key: string, params?: Record<string, string | number>) => translate(language, key, params),
  }
}

export function getLanguageFromStorage(): Language {
  return getStoredLanguage()
}
