import React, { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate } from 'react-router'
import {
  apiFetch,
  deleteAccount,
  changePassword,
  disableMfa,
  enableMfa,
  getLoginHistory,
  getMfaStatus,
  getMySessions,
  provisionMfa,
  revokeSession,
  type AuthSession,
  type LoginHistoryEntry,
} from '../../../../api'
import { toKnowledgeDocVm } from '../../../../shared/api/mappers'
import type { KnowledgeDocVm } from '../../../../shared/api/contracts'
import {
  changePasswordSchema,
  knowledgeDocSchema,
  mfaDisableSchema,
  mfaEnableSchema,
  type ChangePasswordFormValues,
  type KnowledgeDocFormValues,
  type MfaDisableFormValues,
  type MfaEnableFormValues,
} from '../../../../shared/forms/schemas'
import { useUnsavedChangesWarning } from '../../../../shared/forms/useUnsavedChangesWarning'
import { parseKnowledgeDocsPage } from '../../../../shared/api/validators'
import { getErrorKind, getErrorMessage, type ErrorKind } from '../../../../shared/lib/errors'
import { formatGermanDateTime } from '../../../../shared/lib/dateTime'
import { EmptyState } from '../../../../shared/ui/states/EmptyState'
import { ErrorState } from '../../../../shared/ui/states/ErrorState'
import { InlineHint } from '../../../../shared/ui/states/InlineHint'
import { ListSkeleton } from '../../../../shared/ui/states/ListSkeleton'
import { useToast } from '../../../../shared/ui/toast/ToastProvider'
import { useI18n } from '../../../../shared/i18n/i18n'

export default function SettingsPage() {
  const toast = useToast()
  const navigate = useNavigate()
  const { language, setLanguage, t } = useI18n()
  const [docs, setDocs] = useState<KnowledgeDocVm[]>([])
  const [sessions, setSessions] = useState<AuthSession[]>([])
  const [history, setHistory] = useState<LoginHistoryEntry[]>([])
  const [mfaEnabled, setMfaEnabled] = useState(false)
  const [mfaSecret, setMfaSecret] = useState('')
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([])
  const [deleteConfirmation, setDeleteConfirmation] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [errKind, setErrKind] = useState<ErrorKind>('technical')
  const [loading, setLoading] = useState(true)
  const [loadFailed, setLoadFailed] = useState(false)

  const changePasswordForm = useForm<ChangePasswordFormValues>({
    resolver: zodResolver(changePasswordSchema),
    mode: 'onChange',
    defaultValues: { currentPassword: '', newPassword: '' },
  })
  const mfaEnableForm = useForm<MfaEnableFormValues>({
    resolver: zodResolver(mfaEnableSchema),
    mode: 'onChange',
    defaultValues: { code: '' },
  })
  const mfaDisableForm = useForm<MfaDisableFormValues>({
    resolver: zodResolver(mfaDisableSchema),
    mode: 'onChange',
    defaultValues: { password: '', code: '' },
  })

  useUnsavedChangesWarning(
    changePasswordForm.formState.isDirty ||
      mfaEnableForm.formState.isDirty ||
      mfaDisableForm.formState.isDirty
  )

  async function load() {
    try {
      setErr(null)
      setErrKind('technical')
      setLoading(true)
      setLoadFailed(false)
      const d = await apiFetch<unknown>('/knowledge')
      setDocs(
        parseKnowledgeDocsPage(d)
          .map(toKnowledgeDocVm)
          .filter((doc) => Boolean(doc.id))
      )
      const [sessionRows, loginRows, mfa] = await Promise.all([
        getMySessions(),
        getLoginHistory(20),
        getMfaStatus(),
      ])
      setSessions(sessionRows)
      setHistory(loginRows)
      setMfaEnabled(mfa.enabled)
    } catch (e: unknown) {
      setLoadFailed(true)
      setErrKind(getErrorKind(e))
      setErr(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function onChangePassword(values: ChangePasswordFormValues) {
    try {
      setErr(null)
      await changePassword(values.currentPassword, values.newPassword)
      changePasswordForm.reset()
      await load()
      toast.success(t('settings.passwordChanged'))
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErrKind(getErrorKind(e))
      setErr(message)
      toast.error(message)
    }
  }

  async function onProvisionMfa() {
    try {
      setErr(null)
      const res = await provisionMfa()
      setMfaSecret(res.secret)
      toast.success(t('settings.totpCreated'))
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErrKind(getErrorKind(e))
      setErr(message)
      toast.error(message)
    }
  }

  async function onEnableMfa(values: MfaEnableFormValues) {
    try {
      setErr(null)
      const res = await enableMfa(mfaSecret, values.code)
      setRecoveryCodes(res.recovery_codes)
      mfaEnableForm.reset()
      await load()
      toast.success(t('settings.mfaEnabled'))
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErrKind(getErrorKind(e))
      setErr(message)
      toast.error(message)
    }
  }

  async function onDisableMfa(values: MfaDisableFormValues) {
    try {
      setErr(null)
      await disableMfa(values.password, values.code)
      mfaDisableForm.reset()
      setRecoveryCodes([])
      await load()
      toast.success(t('settings.mfaDisabled'))
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErrKind(getErrorKind(e))
      setErr(message)
      toast.error(message)
    }
  }

  async function onRevokeSession(id: string) {
    try {
      setErr(null)
      await revokeSession(id)
      await load()
      toast.success(t('settings.sessionEnded'))
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErrKind(getErrorKind(e))
      setErr(message)
      toast.error(message)
    }
  }

  async function onDeleteAccount() {
    try {
      setErr(null)
      const response = await deleteAccount()
      setDeleteConfirmation('')
      toast.success(response.message)
      navigate('/login')
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErrKind(getErrorKind(e))
      setErr(message)
      toast.error(message)
    }
  }

  async function save(doc: KnowledgeDocVm): Promise<boolean> {
    try {
      setErr(null)
      await apiFetch(`/knowledge/${doc.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          title: doc.title,
          content: doc.content,
          type: doc.type,
          source_name: doc.sourceName || null,
          source_url: doc.sourceUrl || null,
          source_type: doc.sourceType,
          source_review_status: doc.sourceReviewStatus,
          source_review_note: doc.sourceReviewNote || null,
          origin_summary: doc.originSummary || null,
          trust_level: doc.trustLevel,
          is_outdated: doc.isOutdated,
          outdated_reason: doc.outdatedReason || null,
        }),
      })
      await load()
      toast.success(t('settings.documentSaved'))
      return true
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErrKind(getErrorKind(e))
      setErr(message)
      toast.error(message)
      return false
    }
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h2 className="page-title">{t('settings.title')}</h2>
          <div className="page-subtitle">{t('settings.subtitle')}</div>
        </div>
      </div>
      {err && <InlineHint type={errKind} message={err} />}

      {loading && (
        <div className="card section-gap">
          <ListSkeleton rows={5} />
        </div>
      )}

      {!loading && loadFailed && err && (
        <ErrorState
          title={t('settings.loadError')}
          message={err}
          onRetry={() => {
            void load()
          }}
        />
      )}

      {!loading && !loadFailed && (
        <>
          <div className="card section-gap">
            <h3>{t('settings.appLanguageCardTitle')}</h3>
            <div className="muted">{t('settings.appLanguageCardBody')}</div>
            <div className="section-gap">
              <label htmlFor="app-language-select" className="field-label">
                {t('settings.appLanguageLabel')}
              </label>
              <select
                id="app-language-select"
                className="w100"
                value={language}
                onChange={(event) => setLanguage(event.target.value === 'en' ? 'en' : 'de')}
              >
                <option value="de">{t('settings.languageGerman')}</option>
                <option value="en">{t('settings.languageEnglish')}</option>
              </select>
              <div className="muted small mt8">{t('settings.languageDescription')}</div>
            </div>
          </div>

          <div className="card section-gap">
            <h3>{t('settings.accountSecurity')}</h3>
            <div className="muted">
              MFA: {mfaEnabled ? t('settings.mfaActive') : t('settings.mfaInactive')}
            </div>

            <div className="section-gap">
              <label htmlFor="settings-current-password" className="field-label">
                {t('settings.currentPassword')}
              </label>
              <input
                id="settings-current-password"
                className="full-width"
                type="password"
                {...changePasswordForm.register('currentPassword')}
                aria-invalid={Boolean(changePasswordForm.formState.errors.currentPassword?.message)}
                aria-describedby={
                  changePasswordForm.formState.errors.currentPassword?.message
                    ? 'settings-current-password-error'
                    : undefined
                }
              />
              {changePasswordForm.formState.errors.currentPassword?.message && (
                <div id="settings-current-password-error" className="error mt8" role="alert">
                  {changePasswordForm.formState.errors.currentPassword.message}
                </div>
              )}
              <label htmlFor="settings-new-password" className="field-label mt8">
                {t('settings.newPassword')}
              </label>
              <input
                id="settings-new-password"
                className="full-width"
                type="password"
                {...changePasswordForm.register('newPassword')}
                aria-invalid={Boolean(changePasswordForm.formState.errors.newPassword?.message)}
                aria-describedby={
                  changePasswordForm.formState.errors.newPassword?.message
                    ? 'settings-new-password-error'
                    : undefined
                }
              />
              {changePasswordForm.formState.errors.newPassword?.message && (
                <div id="settings-new-password-error" className="error mt8" role="alert">
                  {changePasswordForm.formState.errors.newPassword.message}
                </div>
              )}
              <button
                className="btn mt8"
                onClick={changePasswordForm.handleSubmit(onChangePassword)}
                disabled={
                  !changePasswordForm.formState.isDirty || !changePasswordForm.formState.isValid
                }
              >
                {language === 'en' ? 'Change password' : 'Passwort ändern'}
              </button>
            </div>

            <div className="section-gap">
              <div className="field-label">
                {language === 'en' ? 'Set up MFA' : 'MFA einrichten'}
              </div>
              <button className="btn" onClick={onProvisionMfa}>
                {language === 'en' ? 'Create TOTP secret' : 'TOTP-Secret erzeugen'}
              </button>
              {!!mfaSecret && (
                <div className="muted mt8">
                  {language === 'en' ? 'Secret' : 'Secret'}: {mfaSecret}
                </div>
              )}
              {!!mfaSecret && (
                <>
                  <label htmlFor="settings-mfa-enable-code" className="field-label mt8">
                    {t('settings.totpCode')}
                  </label>
                  <input
                    id="settings-mfa-enable-code"
                    className="full-width"
                    {...mfaEnableForm.register('code')}
                    aria-invalid={Boolean(mfaEnableForm.formState.errors.code?.message)}
                    aria-describedby={
                      mfaEnableForm.formState.errors.code?.message
                        ? 'settings-mfa-enable-code-error'
                        : undefined
                    }
                  />
                  {mfaEnableForm.formState.errors.code?.message && (
                    <div id="settings-mfa-enable-code-error" className="error mt8" role="alert">
                      {mfaEnableForm.formState.errors.code.message}
                    </div>
                  )}
                  <button
                    className="btn mt8"
                    onClick={mfaEnableForm.handleSubmit(onEnableMfa)}
                    disabled={!mfaSecret}
                  >
                    {language === 'en' ? 'Enable MFA' : 'MFA aktivieren'}
                  </button>
                </>
              )}
              {!!recoveryCodes.length && (
                <div className="muted mt8">
                  {language === 'en' ? 'Recovery codes' : 'Recovery-Codes'}:{' '}
                  {recoveryCodes.join(', ')}
                </div>
              )}
            </div>

            {mfaEnabled && (
              <div className="section-gap">
                <div className="field-label">
                  {language === 'en' ? 'Disable MFA' : 'MFA deaktivieren'}
                </div>
                <label htmlFor="settings-mfa-disable-password" className="sr-only">
                  {t('settings.mfaPassword')}
                </label>
                <input
                  id="settings-mfa-disable-password"
                  className="full-width"
                  type="password"
                  placeholder={language === 'en' ? 'Password' : 'Passwort'}
                  {...mfaDisableForm.register('password')}
                  aria-invalid={Boolean(mfaDisableForm.formState.errors.password?.message)}
                  aria-describedby={
                    mfaDisableForm.formState.errors.password?.message
                      ? 'settings-mfa-disable-password-error'
                      : undefined
                  }
                />
                {mfaDisableForm.formState.errors.password?.message && (
                  <div id="settings-mfa-disable-password-error" className="error mt8" role="alert">
                    {mfaDisableForm.formState.errors.password.message}
                  </div>
                )}
                <label htmlFor="settings-mfa-disable-code" className="sr-only">
                  {t('settings.mfaDisableCode')}
                </label>
                <input
                  id="settings-mfa-disable-code"
                  className="full-width mt8"
                  placeholder={
                    language === 'en' ? 'TOTP or recovery code' : 'TOTP oder Recovery-Code'
                  }
                  {...mfaDisableForm.register('code')}
                  aria-invalid={Boolean(mfaDisableForm.formState.errors.code?.message)}
                  aria-describedby={
                    mfaDisableForm.formState.errors.code?.message
                      ? 'settings-mfa-disable-code-error'
                      : undefined
                  }
                />
                {mfaDisableForm.formState.errors.code?.message && (
                  <div id="settings-mfa-disable-code-error" className="error mt8" role="alert">
                    {mfaDisableForm.formState.errors.code.message}
                  </div>
                )}
                <button
                  className="btn danger mt8"
                  onClick={mfaDisableForm.handleSubmit(onDisableMfa)}
                  disabled={!mfaDisableForm.formState.isDirty || !mfaDisableForm.formState.isValid}
                >
                  {language === 'en' ? 'Disable MFA' : 'MFA deaktivieren'}
                </button>
              </div>
            )}
          </div>

          <div className="card section-gap">
            <h3>{language === 'en' ? 'Active sessions' : 'Aktive Sessions'}</h3>
            {!sessions.length && (
              <div className="muted">{language === 'en' ? 'No sessions.' : 'Keine Sessions.'}</div>
            )}
            {!!sessions.length && (
              <table tabIndex={0}>
                <caption className="sr-only">
                  {language === 'en' ? 'List of active sessions' : 'Liste aktiver Sitzungen'}
                </caption>
                <thead>
                  <tr>
                    <th scope="col">{language === 'en' ? 'Device' : 'Gerät'}</th>
                    <th scope="col">IP</th>
                    <th scope="col">{language === 'en' ? 'Last activity' : 'Letzte Aktivität'}</th>
                    <th scope="col">{language === 'en' ? 'Expires' : 'Ablauf'}</th>
                    <th scope="col">{language === 'en' ? 'Action' : 'Aktion'}</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.map((s) => (
                    <tr key={s.id}>
                      <td>
                        {s.device_label || (language === 'en' ? 'Unknown' : 'Unbekannt')}
                        {s.is_current ? (language === 'en' ? ' (current)' : ' (aktuell)') : ''}
                      </td>
                      <td>{s.ip_address || '-'}</td>
                      <td>{formatGermanDateTime(s.last_activity_at)}</td>
                      <td>{formatGermanDateTime(s.expires_at)}</td>
                      <td>
                        {!s.is_current && (
                          <button
                            className="btn danger"
                            onClick={() => onRevokeSession(s.id)}
                            aria-label={
                              language === 'en'
                                ? `End session on ${s.device_label || 'Unknown'}`
                                : `Session auf ${s.device_label || 'Unbekannt'} beenden`
                            }
                          >
                            {language === 'en' ? 'End' : 'Beenden'}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="card section-gap">
            <h3>{language === 'en' ? 'Login history' : 'Anmeldehistorie'}</h3>
            {!history.length && (
              <div className="muted">{language === 'en' ? 'No entries.' : 'Keine Einträge.'}</div>
            )}
            {!!history.length && (
              <table tabIndex={0}>
                <caption className="sr-only">
                  {language === 'en' ? 'Login history' : 'Anmeldehistorie'}
                </caption>
                <thead>
                  <tr>
                    <th scope="col">{language === 'en' ? 'Time' : 'Zeit'}</th>
                    <th scope="col">IP</th>
                    <th scope="col">Status</th>
                    <th scope="col">{language === 'en' ? 'Note' : 'Hinweis'}</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h) => (
                    <tr key={h.id}>
                      <td>{formatGermanDateTime(h.occurred_at)}</td>
                      <td>{h.ip_address || '-'}</td>
                      <td>
                        {h.success
                          ? language === 'en'
                            ? 'Success'
                            : 'Erfolg'
                          : language === 'en'
                            ? 'Failure'
                            : 'Fehler'}
                        {h.suspicious
                          ? language === 'en'
                            ? ' (suspicious)'
                            : ' (verdächtig)'
                          : ''}
                      </td>
                      <td>{h.reason || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="card section-gap">
            <h3>{language === 'en' ? 'Delete account' : 'Account löschen'}</h3>
            <div className="muted">
              {language === 'en'
                ? 'Deletion becomes permanent after 30 days. All active sessions end immediately.'
                : 'Die Löschung wird nach 30 Tagen endgültig ausgeführt. Alle aktiven Sessions werden sofort beendet.'}
            </div>
            <label htmlFor="settings-delete-account-confirm" className="field-label mt8">
              {t('settings.confirmation')}
            </label>
            <input
              id="settings-delete-account-confirm"
              className="full-width"
              value={deleteConfirmation}
              onChange={(event) => setDeleteConfirmation(event.target.value)}
              placeholder={language === 'en' ? 'DELETE' : 'LÖSCHEN'}
              autoComplete="off"
              spellCheck={false}
            />
            <button
              className="btn danger mt8"
              onClick={() => {
                void onDeleteAccount()
              }}
              disabled={
                deleteConfirmation.trim().toUpperCase() !==
                (language === 'en' ? 'DELETE' : 'LÖSCHEN')
              }
            >
              {language === 'en' ? 'Schedule account deletion' : 'Account zur Löschung anmelden'}
            </button>
          </div>

          <div className="section-gap">
            {docs.map((d) => (
              <DocEditor key={d.id} doc={d} onSave={save} />
            ))}
            {!docs.length && (
              <EmptyState
                title={language === 'en' ? 'No documents' : 'Keine Dokumente'}
                message={
                  language === 'en'
                    ? 'There are currently no knowledge documents.'
                    : 'Es sind aktuell keine Wissensdokumente vorhanden.'
                }
              />
            )}
          </div>
        </>
      )}
    </div>
  )
}

type DocEditorProps = {
  doc: KnowledgeDocVm
  onSave: (doc: KnowledgeDocVm) => Promise<boolean>
}

function DocEditor({ doc, onSave }: DocEditorProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty, isValid },
  } = useForm<KnowledgeDocFormValues>({
    resolver: zodResolver(knowledgeDocSchema),
    mode: 'onChange',
    defaultValues: {
      title: doc.title,
      content: doc.content,
      sourceName: doc.sourceName,
      sourceUrl: doc.sourceUrl,
      sourceType: (doc.sourceType as KnowledgeDocFormValues['sourceType']) || 'internal',
      sourceReviewStatus:
        (doc.sourceReviewStatus as KnowledgeDocFormValues['sourceReviewStatus']) || 'pending',
      sourceReviewNote: doc.sourceReviewNote,
      originSummary: doc.originSummary,
      trustLevel: (doc.trustLevel as KnowledgeDocFormValues['trustLevel']) || 'medium',
      isOutdated: doc.isOutdated,
      outdatedReason: doc.outdatedReason,
    },
  })

  useUnsavedChangesWarning(isDirty)

  useEffect(() => {
    reset({
      title: doc.title,
      content: doc.content,
      sourceName: doc.sourceName,
      sourceUrl: doc.sourceUrl,
      sourceType: (doc.sourceType as KnowledgeDocFormValues['sourceType']) || 'internal',
      sourceReviewStatus:
        (doc.sourceReviewStatus as KnowledgeDocFormValues['sourceReviewStatus']) || 'pending',
      sourceReviewNote: doc.sourceReviewNote,
      originSummary: doc.originSummary,
      trustLevel: (doc.trustLevel as KnowledgeDocFormValues['trustLevel']) || 'medium',
      isOutdated: doc.isOutdated,
      outdatedReason: doc.outdatedReason,
    })
  }, [
    doc.id,
    doc.title,
    doc.content,
    doc.sourceName,
    doc.sourceUrl,
    doc.sourceType,
    doc.sourceReviewStatus,
    doc.sourceReviewNote,
    doc.originSummary,
    doc.trustLevel,
    doc.isOutdated,
    doc.outdatedReason,
    reset,
  ])

  async function submit(values: KnowledgeDocFormValues) {
    const saved = await onSave({
      ...doc,
      title: values.title,
      content: values.content,
      sourceName: values.sourceName,
      sourceUrl: values.sourceUrl,
      sourceType: values.sourceType,
      sourceReviewStatus: values.sourceReviewStatus,
      sourceReviewNote: values.sourceReviewNote,
      originSummary: values.originSummary,
      trustLevel: values.trustLevel,
      isOutdated: values.isOutdated,
      outdatedReason: values.outdatedReason,
    })
    if (saved) reset(values)
  }

  return (
    <details
      id={`knowledge-${doc.id}`}
      className="card section-gap no-margin knowledge-editor"
      open={isDirty ? true : undefined}
    >
      <summary>
        <div>
          <div className="pill">{doc.type}</div>
          <div className="title-strong mt8">{doc.title}</div>
          <div className="muted mt8">
            Version {doc.currentVersion} • Quelle-Review: {doc.sourceReviewStatus} • Vertrauen:{' '}
            {doc.trustLevel}
            {doc.isOutdated ? ' • Veraltet' : ''}
          </div>
        </div>
      </summary>
      <div className="knowledge-editor-body">
        <div className="page-header section-gap">
          <div>
            <h3 className="no-margin">Dokument bearbeiten</h3>
            <div className="muted small mt8">Änderungen werden erst mit Speichern übernommen.</div>
          </div>
          <button
            className="btn primary"
            onClick={handleSubmit(submit)}
            disabled={!isDirty || !isValid}
          >
            Speichern
          </button>
        </div>
        <div className="section-gap">
          <label htmlFor={`knowledge-title-${doc.id}`} className="field-label">
            Titel
          </label>
          <input
            id={`knowledge-title-${doc.id}`}
            className="full-width"
            {...register('title')}
            aria-invalid={Boolean(errors.title?.message)}
            aria-describedby={errors.title?.message ? `knowledge-title-${doc.id}-error` : undefined}
          />
          {errors.title?.message && (
            <div id={`knowledge-title-${doc.id}-error`} className="error mt8" role="alert">
              {errors.title.message}
            </div>
          )}
        </div>
        <div className="section-gap">
          <label htmlFor={`knowledge-content-${doc.id}`} className="field-label">
            Inhalt
          </label>
          <textarea
            id={`knowledge-content-${doc.id}`}
            className="full-width"
            {...register('content')}
            rows={10}
            aria-invalid={Boolean(errors.content?.message)}
            aria-describedby={
              errors.content?.message ? `knowledge-content-${doc.id}-error` : undefined
            }
          />
          {errors.content?.message && (
            <div id={`knowledge-content-${doc.id}-error`} className="error mt8" role="alert">
              {errors.content.message}
            </div>
          )}
        </div>

        <div className="section-gap">
          <h4>Quellenverwaltung</h4>
          <label htmlFor={`knowledge-source-name-${doc.id}`} className="field-label">
            Quelle
          </label>
          <input
            id={`knowledge-source-name-${doc.id}`}
            className="full-width"
            {...register('sourceName')}
          />
          <label htmlFor={`knowledge-source-url-${doc.id}`} className="field-label mt8">
            Quellen-URL
          </label>
          <input
            id={`knowledge-source-url-${doc.id}`}
            className="full-width"
            {...register('sourceUrl')}
          />
          <label htmlFor={`knowledge-source-type-${doc.id}`} className="field-label mt8">
            Herkunftstyp
          </label>
          <select
            id={`knowledge-source-type-${doc.id}`}
            className="full-width"
            {...register('sourceType')}
          >
            <option value="internal">intern</option>
            <option value="external">extern</option>
            <option value="customer">kundenseitig</option>
            <option value="legal">rechtlich</option>
            <option value="other">sonstiges</option>
          </select>
          <label htmlFor={`knowledge-source-review-${doc.id}`} className="field-label mt8">
            Review-Status Quelle
          </label>
          <select
            id={`knowledge-source-review-${doc.id}`}
            className="full-width"
            {...register('sourceReviewStatus')}
          >
            <option value="pending">offen</option>
            <option value="approved">freigegeben</option>
            <option value="rejected">abgelehnt</option>
            <option value="needs_update">Update nötig</option>
          </select>
          <label htmlFor={`knowledge-trust-${doc.id}`} className="field-label mt8">
            Vertrauensgrad
          </label>
          <select
            id={`knowledge-trust-${doc.id}`}
            className="full-width"
            {...register('trustLevel')}
          >
            <option value="low">niedrig</option>
            <option value="medium">mittel</option>
            <option value="high">hoch</option>
            <option value="verified">verifiziert</option>
          </select>
          <label htmlFor={`knowledge-origin-summary-${doc.id}`} className="field-label mt8">
            Herkunftszusammenfassung
          </label>
          <textarea
            id={`knowledge-origin-summary-${doc.id}`}
            className="full-width"
            rows={3}
            {...register('originSummary')}
          />
          <label htmlFor={`knowledge-source-note-${doc.id}`} className="field-label mt8">
            Review-Notiz zur Quelle
          </label>
          <textarea
            id={`knowledge-source-note-${doc.id}`}
            className="full-width"
            rows={3}
            {...register('sourceReviewNote')}
          />
        </div>

        <div className="section-gap">
          <h4>Veralterung</h4>
          <label className="field-label" htmlFor={`knowledge-outdated-${doc.id}`}>
            Als veraltet markieren
          </label>
          <input id={`knowledge-outdated-${doc.id}`} type="checkbox" {...register('isOutdated')} />
          <label htmlFor={`knowledge-outdated-reason-${doc.id}`} className="field-label mt8">
            Grund
          </label>
          <textarea
            id={`knowledge-outdated-reason-${doc.id}`}
            className="full-width"
            rows={3}
            {...register('outdatedReason')}
            aria-invalid={Boolean(errors.outdatedReason?.message)}
            aria-describedby={
              errors.outdatedReason?.message
                ? `knowledge-outdated-reason-${doc.id}-error`
                : undefined
            }
          />
          {errors.outdatedReason?.message && (
            <div
              id={`knowledge-outdated-reason-${doc.id}-error`}
              className="error mt8"
              role="alert"
            >
              {errors.outdatedReason.message}
            </div>
          )}
          {doc.outdatedAt && (
            <div className="muted mt8">Seit: {formatGermanDateTime(doc.outdatedAt)}</div>
          )}
        </div>

        <div className="section-gap">
          <h4>Versionshistorie</h4>
          {!doc.versions.length && (
            <div className="muted">Noch keine Versionshistorie vorhanden.</div>
          )}
          {!!doc.versions.length && (
            <table tabIndex={0}>
              <thead>
                <tr>
                  <th scope="col">Version</th>
                  <th scope="col">Zeit</th>
                  <th scope="col">Person</th>
                  <th scope="col">Änderung</th>
                </tr>
              </thead>
              <tbody>
                {doc.versions.map((version) => (
                  <tr key={version.id}>
                    <td>{version.versionNumber}</td>
                    <td>{formatGermanDateTime(version.createdAt, '-')}</td>
                    <td>{version.changedByName || '-'}</td>
                    <td>{version.changeNote || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="section-gap">
          <h4>Genutzte Entwürfe</h4>
          {!doc.draftLinks.length && (
            <div className="muted">Noch mit keinem Entwurf verknüpft.</div>
          )}
          {!!doc.draftLinks.length && (
            <table tabIndex={0}>
              <thead>
                <tr>
                  <th scope="col">Entwurf</th>
                  <th scope="col">Zeit</th>
                  <th scope="col">Verknüpft von</th>
                </tr>
              </thead>
              <tbody>
                {doc.draftLinks.map((link) => (
                  <tr key={link.id}>
                    <td>{link.emailDraftId}</td>
                    <td>{formatGermanDateTime(link.linkedAt, '-')}</td>
                    <td>{link.linkedByName || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </details>
  )
}
