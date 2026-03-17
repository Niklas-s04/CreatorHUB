import React, { useEffect, useState } from 'react'
import { apiFetch, getUsers, type RegistrationRequest, type UserSummary } from '../api'

type Me = {
  id: string
  username: string
  role: 'admin' | 'editor' | 'viewer'
  is_active: boolean
  needs_password_setup: boolean
}

export default function AdminPage() {
  const [me, setMe] = useState<Me | null>(null)
  const [requests, setRequests] = useState<RegistrationRequest[]>([])
  const [users, setUsers] = useState<UserSummary[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    load()
  }, [])

  async function load() {
    setBusy(true)
    setErr(null)
    try {
      const meData = await apiFetch('/auth/me') as Me
      setMe(meData)
      if (meData.role !== 'admin') {
        setRequests([])
        setUsers([])
        return
      }
      const list = await apiFetch('/auth/registration-requests?status_filter=pending') as RegistrationRequest[]
      setRequests(list)
      const userRows = await getUsers()
      setUsers(userRows)
    } catch (e: any) {
      setErr(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  async function decide(id: string, action: 'approve' | 'reject') {
    setErr(null)
    try {
      await apiFetch(`/auth/registration-requests/${id}/${action}`, { method: 'POST' })
      await load()
    } catch (e: any) {
      setErr(e.message || String(e))
    }
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h2 className="page-title">Administration</h2>
          <div className="page-subtitle">Verwalte Registrierungsanfragen zentral.</div>
        </div>
        <button className="btn" onClick={load} disabled={busy}>{busy ? '...' : 'Refresh'}</button>
      </div>

      {err && <div className="error">{err}</div>}

      {me && me.role !== 'admin' && (
        <div className="card">Nur Admin kann Registrierungsanfragen bearbeiten.</div>
      )}

      {me?.role === 'admin' && (
        <>
          <div className="card section-gap">
            <h3>Benutzer</h3>
            {!users.length && <div className="muted">Keine Benutzer.</div>}
            {!!users.length && (
              <table>
                <thead>
                  <tr>
                    <th>Username</th>
                    <th>Rolle</th>
                    <th>MFA</th>
                    <th>Aktive Sessions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <tr key={u.id}>
                      <td>{u.username}</td>
                      <td><span className="pill">{u.role}</span></td>
                      <td>{u.mfa_enabled ? 'Aktiv' : 'Inaktiv'}</td>
                      <td>{u.active_sessions}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="card section-gap">
            <h3>Registrierungsanfragen</h3>
            {!requests.length && <div className="muted">Keine offenen Anfragen.</div>}
            {!!requests.length && (
              <table>
                <thead>
                  <tr>
                    <th>Username</th>
                    <th>Status</th>
                    <th>Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {requests.map(r => (
                    <tr key={r.id}>
                      <td>{r.username}</td>
                      <td><span className="pill">{r.status}</span></td>
                      <td>
                        <div className="table-actions">
                          <button className="btn primary" onClick={() => decide(r.id, 'approve')}>Freigeben</button>
                          <button className="btn danger" onClick={() => decide(r.id, 'reject')}>Ablehnen</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  )
}
