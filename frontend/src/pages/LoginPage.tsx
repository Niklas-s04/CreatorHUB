import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../api'

export default function LoginPage() {
  const nav = useNavigate()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('admin_change_me')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setErr(null)
    setBusy(true)
    try {
      await login(username, password)
      nav('/')
    } catch (e: any) {
      setErr(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container max480 pt60">
      <div className="card">
        <div className="row between">
          <h2>Login</h2>
          <span className="muted small">CreatorHUB</span>
        </div>

        <div className="muted small">Standard: admin / admin_change_me (bitte ändern).</div>

        <hr />

        <form onSubmit={onSubmit} className="stack">
          <div>
            <div className="muted small" style={{ marginBottom: 6 }}>Username</div>
            <input className="w100" value={username} onChange={e => setUsername(e.target.value)} />
          </div>

          <div>
            <div className="muted small" style={{ marginBottom: 6 }}>Password</div>
            <input className="w100" type="password" value={password} onChange={e => setPassword(e.target.value)} />
          </div>

          {err && <div className="error">{err}</div>}

          <button className="btn primary w100" disabled={busy}>
            {busy ? '...' : 'Login'}
          </button>
        </form>
      </div>
    </div>
  )
}