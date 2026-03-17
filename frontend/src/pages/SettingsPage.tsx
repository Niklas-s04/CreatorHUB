import React, { useEffect, useState } from 'react'
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
} from '../api'

export default function SettingsPage() {
  const [docs, setDocs] = useState<any[]>([])
  const [sessions, setSessions] = useState<AuthSession[]>([])
  const [history, setHistory] = useState<LoginHistoryEntry[]>([])
  const [mfaEnabled, setMfaEnabled] = useState(false)
  const [mfaSecret, setMfaSecret] = useState('')
  const [mfaCode, setMfaCode] = useState('')
  const [disableCode, setDisableCode] = useState('')
  const [disablePassword, setDisablePassword] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([])
  const [err, setErr] = useState<string | null>(null)

  async function load() {
    try {
      setErr(null)
      const d = await apiFetch('/knowledge')
      setDocs(d)
      const [sessionRows, loginRows, mfa] = await Promise.all([
        getMySessions(),
        getLoginHistory(20),
        getMfaStatus(),
      ])
      setSessions(sessionRows)
      setHistory(loginRows)
      setMfaEnabled(mfa.enabled)
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  useEffect(() => { load() }, [])

  async function onChangePassword() {
    try {
      setErr(null)
      await changePassword(currentPassword, newPassword)
      setCurrentPassword('')
      setNewPassword('')
      await load()
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  async function onProvisionMfa() {
    try {
      setErr(null)
      const res = await provisionMfa()
      setMfaSecret(res.secret)
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  async function onEnableMfa() {
    try {
      setErr(null)
      const res = await enableMfa(mfaSecret, mfaCode)
      setRecoveryCodes(res.recovery_codes)
      setMfaCode('')
      await load()
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  async function onDisableMfa() {
    try {
      setErr(null)
      await disableMfa(disablePassword, disableCode)
      setDisableCode('')
      setDisablePassword('')
      setRecoveryCodes([])
      await load()
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  async function onRevokeSession(id: string) {
    try {
      setErr(null)
      await revokeSession(id)
      await load()
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  async function save(doc: any) {
    try {
      setErr(null)
      await apiFetch(`/knowledge/${doc.id}`, { method: 'PATCH', body: JSON.stringify({ title: doc.title, content: doc.content, type: doc.type }) })
      await load()
    } catch (e: any) {
      setErr(e.message || String(e))
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
      {err && <div className="error">{err}</div>}
      <div className="card section-gap">
        <h3>Account-Sicherheit</h3>
        <div className="muted">MFA: {mfaEnabled ? 'Aktiv' : 'Inaktiv'}</div>

        <div className="section-gap">
          <div className="field-label">Aktuelles Passwort</div>
          <input className="full-width" type="password" value={currentPassword} onChange={e => setCurrentPassword(e.target.value)} />
          <div className="field-label mt8">Neues Passwort</div>
          <input className="full-width" type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} />
          <button className="btn mt8" onClick={onChangePassword}>Passwort ändern</button>
        </div>

        <div className="section-gap">
          <div className="field-label">MFA einrichten</div>
          <button className="btn" onClick={onProvisionMfa}>TOTP-Secret erzeugen</button>
          {!!mfaSecret && <div className="muted mt8">Secret: {mfaSecret}</div>}
          {!!mfaSecret && (
            <>
              <div className="field-label mt8">TOTP-Code</div>
              <input className="full-width" value={mfaCode} onChange={e => setMfaCode(e.target.value)} />
              <button className="btn mt8" onClick={onEnableMfa}>MFA aktivieren</button>
            </>
          )}
          {!!recoveryCodes.length && <div className="muted mt8">Recovery-Codes: {recoveryCodes.join(', ')}</div>}
        </div>

        {mfaEnabled && (
          <div className="section-gap">
            <div className="field-label">MFA deaktivieren</div>
            <input className="full-width" type="password" placeholder="Passwort" value={disablePassword} onChange={e => setDisablePassword(e.target.value)} />
            <input className="full-width mt8" placeholder="TOTP oder Recovery-Code" value={disableCode} onChange={e => setDisableCode(e.target.value)} />
            <button className="btn danger mt8" onClick={onDisableMfa}>MFA deaktivieren</button>
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
        {!docs.length && <div className="empty-state">Keine Docs.</div>}
      </div>
    </div>
  )
}

function DocEditor({ doc, onSave }: any) {
  const [title, setTitle] = useState(doc.title)
  const [content, setContent] = useState(doc.content)

  return (
    <div className="card section-gap no-margin">
      <div className="page-header no-margin">
        <div>
          <div className="pill">{doc.type}</div>
          <div className="title-strong mt8">{doc.title}</div>
        </div>
        <button className="btn" onClick={() => onSave({ ...doc, title, content })}>Speichern</button>
      </div>
      <div className="section-gap">
        <div className="field-label">Titel</div>
        <input className="full-width" value={title} onChange={e => setTitle(e.target.value)} />
      </div>
      <div className="section-gap">
        <div className="field-label">Inhalt</div>
        <textarea className="full-width" value={content} onChange={e => setContent(e.target.value)} rows={10} />
      </div>
    </div>
  )
}