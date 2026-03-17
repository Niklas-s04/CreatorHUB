import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { confirmPasswordReset, getBootstrapStatus, login, requestPasswordReset, requestRegistration, setupAdminPassword } from '../api'

type Mode = 'login' | 'register' | 'setup' | 'reset'

function formatError(err: unknown): string {
  const msg = err instanceof Error ? err.message : String(err)
  try {
    const parsed = JSON.parse(msg)
    if (typeof parsed?.detail === 'string') return parsed.detail
  } catch {
  }
  return msg
}

export default function LoginPage() {
  const nav = useNavigate()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [password2, setPassword2] = useState('')
  const [otp, setOtp] = useState('')
  const [resetToken, setResetToken] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState<Mode>('login')
  const [adminUsername, setAdminUsername] = useState('admin')
  const [bootstrapToken, setBootstrapToken] = useState('')

  React.useEffect(() => {
    ;(async () => {
      try {
        const token = localStorage.getItem('bootstrap_token') || ''
        if (!token) return
        const status = await getBootstrapStatus(token)
        setAdminUsername(status.admin_username)
        if (status.needs_password_setup) {
          setMode('setup')
          setUsername(status.admin_username)
          setBootstrapToken(token)
        }
      } catch {
      }
    })()
  }, [])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    setMsg(null)
    setBusy(true)
    try {
      if (mode === 'setup') {
        if (!bootstrapToken.trim()) throw new Error('Bootstrap-Token erforderlich')
        if (password !== password2) throw new Error('Passwörter stimmen nicht überein')
        await setupAdminPassword(password, bootstrapToken)
        localStorage.removeItem('bootstrap_token')
        nav('/admin')
      } else if (mode === 'register') {
        if (password !== password2) throw new Error('Passwörter stimmen nicht überein')
        await requestRegistration(username, password)
        setMsg('Registrierungsanfrage wurde an den Admin gesendet.')
        setPassword('')
        setPassword2('')
      } else if (mode === 'reset') {
        if (resetToken.trim()) {
          if (password !== password2) throw new Error('Passwörter stimmen nicht überein')
          await confirmPasswordReset(resetToken, password)
          setMsg('Passwort wurde zurückgesetzt. Bitte einloggen.')
          setMode('login')
          setPassword('')
          setPassword2('')
          setResetToken('')
        } else {
          const res = await requestPasswordReset(username)
          setMsg(res.reset_token ? `Reset-Token: ${res.reset_token}` : 'Falls der Benutzer existiert, wurde ein Reset ausgelöst.')
        }
      } else {
        await login(username, password, otp)
        nav('/')
      }
    } catch (e: any) {
      setErr(formatError(e))
    } finally {
      setBusy(false)
    }
  }

  async function checkBootstrap() {
    setErr(null)
    setMsg(null)
    try {
      if (!bootstrapToken.trim()) throw new Error('Bootstrap-Token erforderlich')
      const status = await getBootstrapStatus(bootstrapToken)
      if (!status.needs_password_setup) {
        setMsg('Erstsetup bereits abgeschlossen.')
        return
      }
      setAdminUsername(status.admin_username)
      setMode('setup')
      setUsername(status.admin_username)
      setMsg('Erstsetup freigeschaltet.')
    } catch (e: any) {
      setErr(formatError(e))
    }
  }

  return (
    <div className="login-shell">
      <div className="card login-card">
        <div className="page-header no-margin">
          <h2 className="page-title">Login</h2>
          <span className="muted small">CreatorHUB</span>
        </div>

        {mode !== 'setup' && (
          <div className="mode-switch">
            <button className={`btn ${mode === 'login' ? 'primary' : ''}`} type="button" onClick={() => { setMode('login'); setErr(null); setMsg(null) }}>Login</button>
            <button className={`btn ${mode === 'register' ? 'primary' : ''}`} type="button" onClick={() => { setMode('register'); setErr(null); setMsg(null) }}>Registrieren</button>
            <button className={`btn ${mode === 'reset' ? 'primary' : ''}`} type="button" onClick={() => { setMode('reset'); setErr(null); setMsg(null) }}>Passwort-Reset</button>
          </div>
        )}

        <div className="section-gap">
          <div className="field-label">Bootstrap-Token (nur Erstsetup)</div>
          <input
            className="w100"
            value={bootstrapToken}
            onChange={e => {
              const value = e.target.value
              setBootstrapToken(value)
              localStorage.setItem('bootstrap_token', value)
            }}
            placeholder="Install-Token"
          />
          <button className="btn mt8" type="button" onClick={checkBootstrap}>Erstsetup prüfen</button>
        </div>

        {mode === 'setup' ? (
          <div className="muted small">Erststart: Admin-Passwort für Benutzer {adminUsername} setzen.</div>
        ) : (
          <div className="muted small">Bei Registrierung wird eine Anfrage an den Admin gestellt.</div>
        )}

        <hr />

        <form onSubmit={onSubmit} className="stack">
          <div>
            <div className="field-label">Username</div>
            <input className="w100" value={mode === 'setup' ? adminUsername : username} onChange={e => setUsername(e.target.value)} disabled={mode === 'setup'} />
          </div>

          <div>
            <div className="field-label">Password</div>
            <input className="w100" type="password" value={password} onChange={e => setPassword(e.target.value)} />
          </div>

          {mode === 'login' && (
            <div>
              <div className="field-label">MFA-Code (optional)</div>
              <input className="w100" value={otp} onChange={e => setOtp(e.target.value)} placeholder="TOTP oder Recovery-Code" />
            </div>
          )}

          {(mode === 'setup' || mode === 'register' || mode === 'reset') && (
            <div>
              <div className="field-label">Password wiederholen</div>
              <input className="w100" type="password" value={password2} onChange={e => setPassword2(e.target.value)} />
            </div>
          )}

          {mode === 'reset' && (
            <div>
              <div className="field-label">Reset-Token (optional für Bestätigung)</div>
              <input className="w100" value={resetToken} onChange={e => setResetToken(e.target.value)} placeholder="Token einfügen, um neues Passwort zu setzen" />
            </div>
          )}

          {err && <div className="error">{err}</div>}
          {msg && <div className="muted">{msg}</div>}

          <button className="btn primary w100" disabled={busy}>
            {busy ? '...' : mode === 'setup' ? 'Admin-Passwort setzen' : mode === 'register' ? 'Anfrage senden' : mode === 'reset' ? (resetToken.trim() ? 'Passwort setzen' : 'Reset anfordern') : 'Login'}
          </button>
        </form>
      </div>
    </div>
  )
}