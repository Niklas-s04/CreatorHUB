import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getBootstrapStatus, login, requestRegistration, setupAdminPassword } from '../api'

type Mode = 'login' | 'register' | 'setup'

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
  const [err, setErr] = useState<string | null>(null)
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState<Mode>('login')
  const [adminUsername, setAdminUsername] = useState('admin')

  React.useEffect(() => {
    ;(async () => {
      try {
        const status = await getBootstrapStatus()
        setAdminUsername(status.admin_username)
        if (status.needs_password_setup) {
          setMode('setup')
          setUsername(status.admin_username)
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
        if (password !== password2) throw new Error('Passwörter stimmen nicht überein')
        await setupAdminPassword(password)
        nav('/admin')
      } else if (mode === 'register') {
        if (password !== password2) throw new Error('Passwörter stimmen nicht überein')
        await requestRegistration(username, password)
        setMsg('Registrierungsanfrage wurde an den Admin gesendet.')
        setPassword('')
        setPassword2('')
      } else {
        await login(username, password)
        nav('/')
      }
    } catch (e: any) {
      setErr(formatError(e))
    } finally {
      setBusy(false)
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
          </div>
        )}

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

          {(mode === 'setup' || mode === 'register') && (
            <div>
              <div className="field-label">Password wiederholen</div>
              <input className="w100" type="password" value={password2} onChange={e => setPassword2(e.target.value)} />
            </div>
          )}

          {err && <div className="error">{err}</div>}
          {msg && <div className="muted">{msg}</div>}

          <button className="btn primary w100" disabled={busy}>
            {busy ? '...' : mode === 'setup' ? 'Admin-Passwort setzen' : mode === 'register' ? 'Anfrage senden' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  )
}