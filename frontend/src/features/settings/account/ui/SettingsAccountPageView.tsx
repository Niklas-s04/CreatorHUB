import React, { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  apiFetch,
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
import { parseKnowledgeDocsDtoArray } from '../../../../shared/api/validators'
import { getErrorKind, getErrorMessage, type ErrorKind } from '../../../../shared/lib/errors'
import { EmptyState } from '../../../../shared/ui/states/EmptyState'
import { ErrorState } from '../../../../shared/ui/states/ErrorState'
import { InlineHint } from '../../../../shared/ui/states/InlineHint'
import { ListSkeleton } from '../../../../shared/ui/states/ListSkeleton'
import { useToast } from '../../../../shared/ui/toast/ToastProvider'

export default function SettingsPage() {
  const toast = useToast()
  const [docs, setDocs] = useState<KnowledgeDocVm[]>([])
  const [sessions, setSessions] = useState<AuthSession[]>([])
  const [history, setHistory] = useState<LoginHistoryEntry[]>([])
  const [mfaEnabled, setMfaEnabled] = useState(false)
  const [mfaSecret, setMfaSecret] = useState('')
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [errKind, setErrKind] = useState<ErrorKind>('technical')
  const [loading, setLoading] = useState(true)

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
    changePasswordForm.formState.isDirty || mfaEnableForm.formState.isDirty || mfaDisableForm.formState.isDirty
  )

  async function load() {
    try {
      setErr(null)
      setErrKind('technical')
      setLoading(true)
      const d = await apiFetch<unknown>('/knowledge')
      setDocs(parseKnowledgeDocsDtoArray(d).map(toKnowledgeDocVm).filter(doc => Boolean(doc.id)))
      const [sessionRows, loginRows, mfa] = await Promise.all([
        getMySessions(),
        getLoginHistory(20),
        getMfaStatus(),
      ])
      setSessions(sessionRows)
      setHistory(loginRows)
      setMfaEnabled(mfa.enabled)
    } catch (e: unknown) {
      setErrKind(getErrorKind(e))
      setErr(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  async function onChangePassword(values: ChangePasswordFormValues) {
    try {
      setErr(null)
      await changePassword(values.currentPassword, values.newPassword)
      changePasswordForm.reset()
      await load()
      toast.success('Passwort erfolgreich geändert')
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
      toast.success('TOTP-Secret wurde erzeugt')
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
      toast.success('MFA wurde aktiviert')
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
      toast.success('MFA wurde deaktiviert')
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
      toast.success('Session beendet')
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErrKind(getErrorKind(e))
      setErr(message)
      toast.error(message)
    }
  }

  async function save(doc: KnowledgeDocVm) {
    try {
      setErr(null)
      await apiFetch(`/knowledge/${doc.id}`, { method: 'PATCH', body: JSON.stringify({ title: doc.title, content: doc.content, type: doc.type }) })
      await load()
      toast.success('Dokument gespeichert')
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErrKind(getErrorKind(e))
      setErr(message)
      toast.error(message)
    }
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h2 className="page-title">Einstellungen</h2>
          <div className="page-subtitle">
            Brand Voice / Policy / Templates für den E-Mail-Assistenten.
          </div>
        </div>
      </div>
      {err && <InlineHint type={errKind} message={err} />}

      {loading && (
        <div className="card section-gap">
          <ListSkeleton rows={5} />
        </div>
      )}

      {!loading && err && (
        <ErrorState
          title="Einstellungen konnten nicht geladen werden"
          message={err}
          onRetry={() => {
            void load()
          }}
        />
      )}

      {!loading && !err && (
        <>
      <div className="card section-gap">
        <h3>Account-Sicherheit</h3>
        <div className="muted">MFA: {mfaEnabled ? 'Aktiv' : 'Inaktiv'}</div>

        <div className="section-gap">
          <div className="field-label">Aktuelles Passwort</div>
          <input className="full-width" type="password" {...changePasswordForm.register('currentPassword')} />
          {changePasswordForm.formState.errors.currentPassword?.message && (
            <div className="error mt8">{changePasswordForm.formState.errors.currentPassword.message}</div>
          )}
          <div className="field-label mt8">Neues Passwort</div>
          <input className="full-width" type="password" {...changePasswordForm.register('newPassword')} />
          {changePasswordForm.formState.errors.newPassword?.message && (
            <div className="error mt8">{changePasswordForm.formState.errors.newPassword.message}</div>
          )}
          <button
            className="btn mt8"
            onClick={changePasswordForm.handleSubmit(onChangePassword)}
            disabled={!changePasswordForm.formState.isDirty || !changePasswordForm.formState.isValid}
          >
            Passwort ändern
          </button>
        </div>

        <div className="section-gap">
          <div className="field-label">MFA einrichten</div>
          <button className="btn" onClick={onProvisionMfa}>TOTP-Secret erzeugen</button>
          {!!mfaSecret && <div className="muted mt8">Secret: {mfaSecret}</div>}
          {!!mfaSecret && (
            <>
              <div className="field-label mt8">TOTP-Code</div>
              <input className="full-width" {...mfaEnableForm.register('code')} />
              {mfaEnableForm.formState.errors.code?.message && (
                <div className="error mt8">{mfaEnableForm.formState.errors.code.message}</div>
              )}
              <button
                className="btn mt8"
                onClick={mfaEnableForm.handleSubmit(onEnableMfa)}
                disabled={!mfaSecret || !mfaEnableForm.formState.isDirty || !mfaEnableForm.formState.isValid}
              >
                MFA aktivieren
              </button>
            </>
          )}
          {!!recoveryCodes.length && <div className="muted mt8">Recovery-Codes: {recoveryCodes.join(', ')}</div>}
        </div>

        {mfaEnabled && (
          <div className="section-gap">
            <div className="field-label">MFA deaktivieren</div>
            <input className="full-width" type="password" placeholder="Passwort" {...mfaDisableForm.register('password')} />
            {mfaDisableForm.formState.errors.password?.message && (
              <div className="error mt8">{mfaDisableForm.formState.errors.password.message}</div>
            )}
            <input className="full-width mt8" placeholder="TOTP oder Recovery-Code" {...mfaDisableForm.register('code')} />
            {mfaDisableForm.formState.errors.code?.message && (
              <div className="error mt8">{mfaDisableForm.formState.errors.code.message}</div>
            )}
            <button
              className="btn danger mt8"
              onClick={mfaDisableForm.handleSubmit(onDisableMfa)}
              disabled={!mfaDisableForm.formState.isDirty || !mfaDisableForm.formState.isValid}
            >
              MFA deaktivieren
            </button>
          </div>
        )}
      </div>

      <div className="card section-gap">
        <h3>Aktive Sessions</h3>
        {!sessions.length && <div className="muted">Keine Sessions.</div>}
        {!!sessions.length && (
          <table>
            <thead>
              <tr>
                <th>Gerät</th>
                <th>IP</th>
                <th>Letzte Aktivität</th>
                <th>Ablauf</th>
                <th>Aktion</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map(s => (
                <tr key={s.id}>
                  <td>{s.device_label || 'Unbekannt'}{s.is_current ? ' (aktuell)' : ''}</td>
                  <td>{s.ip_address || '-'}</td>
                  <td>{new Date(s.last_activity_at).toLocaleString()}</td>
                  <td>{new Date(s.expires_at).toLocaleString()}</td>
                  <td>{!s.is_current && <button className="btn danger" onClick={() => onRevokeSession(s.id)}>Beenden</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card section-gap">
        <h3>Anmeldehistorie</h3>
        {!history.length && <div className="muted">Keine Einträge.</div>}
        {!!history.length && (
          <table>
            <thead>
              <tr>
                <th>Zeit</th>
                <th>IP</th>
                <th>Status</th>
                <th>Hinweis</th>
              </tr>
            </thead>
            <tbody>
              {history.map(h => (
                <tr key={h.id}>
                  <td>{new Date(h.occurred_at).toLocaleString()}</td>
                  <td>{h.ip_address || '-'}</td>
                  <td>{h.success ? 'Erfolg' : 'Fehler'}{h.suspicious ? ' (verdächtig)' : ''}</td>
                  <td>{h.reason || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="section-gap">
        {docs.map(d => <DocEditor key={d.id} doc={d} onSave={save} />)}
        {!docs.length && <EmptyState title="Keine Dokumente" message="Es sind aktuell keine Wissensdokumente vorhanden." />}
      </div>
        </>
      )}
    </div>
  )
}

type DocEditorProps = {
  doc: KnowledgeDocVm
  onSave: (doc: KnowledgeDocVm) => void
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
    defaultValues: { title: doc.title, content: doc.content },
  })

  useUnsavedChangesWarning(isDirty)

  useEffect(() => {
    reset({ title: doc.title, content: doc.content })
  }, [doc.id, doc.title, doc.content, reset])

  function submit(values: KnowledgeDocFormValues) {
    onSave({ ...doc, title: values.title, content: values.content })
    reset(values)
  }

  return (
    <div className="card section-gap no-margin">
      <div className="page-header no-margin">
        <div>
          <div className="pill">{doc.type}</div>
          <div className="title-strong mt8">{doc.title}</div>
        </div>
        <button className="btn" onClick={handleSubmit(submit)} disabled={!isDirty || !isValid}>Speichern</button>
      </div>
      <div className="section-gap">
        <div className="field-label">Titel</div>
        <input className="full-width" {...register('title')} />
        {errors.title?.message && <div className="error mt8">{errors.title.message}</div>}
      </div>
      <div className="section-gap">
        <div className="field-label">Inhalt</div>
        <textarea className="full-width" {...register('content')} rows={10} />
        {errors.content?.message && <div className="error mt8">{errors.content.message}</div>}
      </div>
    </div>
  )
}