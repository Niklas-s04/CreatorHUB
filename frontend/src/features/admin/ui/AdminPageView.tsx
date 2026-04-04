import React, { useEffect, useMemo, useState } from 'react'
import { getErrorMessage } from '../../../shared/lib/errors'
import { useAuthz } from '../../../shared/hooks/useAuthz'
import { EmptyState } from '../../../shared/ui/states/EmptyState'
import { ErrorState } from '../../../shared/ui/states/ErrorState'
import { ListSkeleton } from '../../../shared/ui/states/ListSkeleton'
import { useToast } from '../../../shared/ui/toast/ToastProvider'
import {
  useDecideRegistrationRequestMutation,
  useAdminRoleAuditQuery,
  useAdminUserActionsMutation,
  useAdminUserSessionsQuery,
  usePendingRegistrationRequestsQuery,
  useRegistrationRequestHistoryQuery,
  useUsersQuery,
} from '../../../shared/api/queries/admin'
import type { AdminSession, RegistrationRequest, UserSummary } from '../../../api'

type RoleAuditEntry = {
  id: string
  action: string
  entity_type: string
  entity_id: string | null
  description: string | null
  actor_name: string | null
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
  meta: Record<string, unknown> | null
  created_at: string
}

export default function AdminPage() {
  const toast = useToast()
  const { me, hasPermission, loading: authzLoading, error: authzError, reload: reloadAuthz } = useAuthz()
  const [err, setErr] = useState<string | null>(null)
  const [adminResetToken, setAdminResetToken] = useState<string | null>(null)
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)
  const [rejectionReasons, setRejectionReasons] = useState<Record<string, string>>({})

  const canApprove = hasPermission('user.approve_registration')
  const canReadUsers = hasPermission('user.read')
  const canManageUsers = hasPermission('user.manage')

  const requestsQuery = usePendingRegistrationRequestsQuery(!authzLoading && canApprove)
  const requestHistoryQuery = useRegistrationRequestHistoryQuery(!authzLoading && canApprove)
  const usersQuery = useUsersQuery(!authzLoading && canReadUsers)
  const decideMutation = useDecideRegistrationRequestMutation()
  const userSessionsQuery = useAdminUserSessionsQuery(selectedUserId, !authzLoading && canReadUsers)
  const roleAuditQuery = useAdminRoleAuditQuery(selectedUserId, !authzLoading && canReadUsers)
  const adminActions = useAdminUserActionsMutation()

  const busy =
    authzLoading ||
    requestsQuery.isFetching ||
    usersQuery.isFetching ||
    decideMutation.isPending ||
    adminActions.passwordReset.isPending ||
    adminActions.lock.isPending ||
    adminActions.unlock.isPending
  const queryErr = useMemo(() => {
    if (requestsQuery.error) return getErrorMessage(requestsQuery.error)
    if (requestHistoryQuery.error) return getErrorMessage(requestHistoryQuery.error)
    if (usersQuery.error) return getErrorMessage(usersQuery.error)
    return null
  }, [requestsQuery.error, requestHistoryQuery.error, usersQuery.error])
  const detailErr = useMemo(() => {
    if (userSessionsQuery.error) return getErrorMessage(userSessionsQuery.error)
    if (roleAuditQuery.error) return getErrorMessage(roleAuditQuery.error)
    return null
  }, [userSessionsQuery.error, roleAuditQuery.error])

  const requests: RegistrationRequest[] = canApprove ? (requestsQuery.data ?? []) : []
  const requestHistory: RegistrationRequest[] = canApprove ? (requestHistoryQuery.data ?? []) : []
  const users: UserSummary[] = canReadUsers ? (usersQuery.data ?? []) : []
  const firstUserId = users[0]?.id ?? null
  const selectedUser: UserSummary | null = selectedUserId ? users.find(user => user.id === selectedUserId) ?? null : null
  const userSessions: AdminSession[] = userSessionsQuery.data ?? []
  const roleAudits: RoleAuditEntry[] = (roleAuditQuery.data ?? []) as RoleAuditEntry[]

  useEffect(() => {
    if (!selectedUserId && firstUserId) {
      setSelectedUserId(firstUserId)
    }
  }, [selectedUserId, firstUserId])

  async function decide(id: string, action: 'approve' | 'reject') {
    setErr(null)
    try {
      const reason = rejectionReasons[id]?.trim() || ''
      await decideMutation.mutateAsync({ id, action, reason })
      toast.success(`Anfrage wurde ${action === 'approve' ? 'freigegeben' : 'abgelehnt'}`)
      if (action === 'reject') {
        setRejectionReasons(prev => ({ ...prev, [id]: '' }))
      }
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErr(message)
      toast.error(message)
    }
  }

  async function refreshAll() {
    await reloadAuthz()
    const detailRefetches = selectedUserId
      ? [userSessionsQuery.refetch(), roleAuditQuery.refetch()]
      : []
    await Promise.all([requestsQuery.refetch(), requestHistoryQuery.refetch(), usersQuery.refetch(), ...detailRefetches])
  }

  async function resetPassword(userId: string) {
    setErr(null)
    setAdminResetToken(null)
    try {
      const response = await adminActions.passwordReset.mutateAsync({ userId })
      setAdminResetToken(response.reset_token)
      toast.success('Passwort-Reset ausgelöst')
      await refreshAll()
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErr(message)
      toast.error(message)
    }
  }

  async function lockAccount(userId: string) {
    setErr(null)
    try {
      await adminActions.lock.mutateAsync({ userId })
      toast.success('Benutzer gesperrt')
      await refreshAll()
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErr(message)
      toast.error(message)
    }
  }

  async function unlockAccount(userId: string) {
    setErr(null)
    try {
      await adminActions.unlock.mutateAsync({ userId })
      toast.success('Benutzer entsperrt')
      await refreshAll()
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErr(message)
      toast.error(message)
    }
  }

  function selectUser(userId: string) {
    setSelectedUserId(userId)
    setAdminResetToken(null)
  }

  function formatDate(value: string | null | undefined) {
    if (!value) return '–'
    try {
      return new Date(value).toLocaleString('de-DE')
    } catch {
      return value
    }
  }

  function formatSessionStatus(session: { revoked_at: string | null; expires_at: string; is_current: boolean }) {
    if (session.revoked_at) return 'Revoked'
    if (new Date(session.expires_at).getTime() <= Date.now()) return 'Expired'
    if (session.is_current) return 'Current'
    return 'Active'
  }

  function renderPermissionPills(permissions: string[], limit = permissions.length) {
    const visible = permissions.slice(0, limit)
    const hidden = permissions.length - visible.length
    return (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
        {visible.map(permission => (
          <span key={permission} className="pill">{permission}</span>
        ))}
        {hidden > 0 && <span className="pill">+{hidden}</span>}
      </div>
    )
  }

  function renderStatusPills(user: NonNullable<typeof selectedUser> | (typeof users)[number]) {
    const pills: Array<{ label: string; tone?: 'primary' | 'danger' }> = []
    if (!user.is_active) pills.push({ label: 'Inaktiv', tone: 'danger' })
    else if (user.locked_until && new Date(user.locked_until).getTime() > Date.now()) {
      pills.push({ label: `Gesperrt bis ${formatDate(user.locked_until)}`, tone: 'danger' })
    } else {
      pills.push({ label: 'Aktiv', tone: 'primary' })
    }
    if (user.needs_password_setup) pills.push({ label: 'Passwort-Reset offen' })
    if (user.mfa_enabled) pills.push({ label: 'MFA aktiv' })
    else pills.push({ label: 'MFA inaktiv' })

    return (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
        {pills.map(pill => (
          <span key={pill.label} className={`pill ${pill.tone ? pill.tone : ''}`.trim()}>{pill.label}</span>
        ))}
      </div>
    )
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h2 className="page-title">Administration</h2>
          <div className="page-subtitle">Verwalte Registrierungsanfragen zentral.</div>
        </div>
        <button
          className="btn"
          onClick={() => {
            void refreshAll()
          }}
          disabled={busy || authzLoading}
        >
          {busy || authzLoading ? '...' : 'Refresh'}
        </button>
      </div>

      {authzError && <div className="error">{authzError}</div>}
      {queryErr && (
        <ErrorState
          title="Admin-Daten konnten nicht geladen werden"
          message={queryErr}
          onRetry={() => {
            void Promise.all([requestsQuery.refetch(), requestHistoryQuery.refetch(), usersQuery.refetch()])
          }}
        />
      )}
      {err && <div className="error">{err}</div>}

      {busy && !requests.length && !users.length && <ListSkeleton rows={4} />}

      {me && !hasPermission('user.approve_registration') && !hasPermission('user.read') && (
        <div className="card">Nur Admin kann Registrierungsanfragen bearbeiten.</div>
      )}

      {me && (
        <>
          {hasPermission('user.read') && (
            <div className="card section-gap">
              <div className="page-header no-margin">
                <div>
                  <h3>Benutzer</h3>
                  <div className="muted small">Status, Rechte, MFA und Aktivität auf einen Blick.</div>
                </div>
                {canManageUsers && <span className="pill">Verwaltung aktiv</span>}
              </div>
              {!users.length && <EmptyState title="Keine Benutzer" message="Es sind aktuell keine Benutzereinträge verfügbar." />}
              {!!users.length && (
                <table>
                  <caption className="sr-only">Benutzerübersicht</caption>
                  <thead>
                    <tr>
                      <th scope="col">Benutzer</th>
                      <th scope="col">Status</th>
                      <th scope="col">Rolle / Rechte</th>
                      <th scope="col">MFA</th>
                      <th scope="col">Letzte Aktivität</th>
                      <th scope="col">Sessions</th>
                      <th scope="col">Aktionen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map(user => (
                      <tr key={user.id} id={`user-${user.id}`}>
                        <td>
                          <button
                            type="button"
                            className="btn"
                            onClick={() => selectUser(user.id)}
                            aria-label={`Details für ${user.username} anzeigen`}
                          >
                            {user.username}
                          </button>
                        </td>
                        <td>{renderStatusPills(user)}</td>
                        <td>
                          <div className="stack">
                            <span className="pill">{user.role}</span>
                            {renderPermissionPills(user.permissions, 4)}
                          </div>
                        </td>
                        <td>{user.mfa_enabled ? 'Aktiv' : 'Inaktiv'}</td>
                        <td>{formatDate(user.last_activity_at)}</td>
                        <td>{user.active_sessions}</td>
                        <td>
                          <div className="table-actions">
                            <button className="btn" onClick={() => selectUser(user.id)}>Sessions</button>
                            {canManageUsers && (
                              <>
                                <button className="btn" onClick={() => void resetPassword(user.id)}>Passwort-Reset</button>
                                {user.locked_until && new Date(user.locked_until).getTime() > Date.now() ? (
                                  <button className="btn primary" onClick={() => void unlockAccount(user.id)}>Entsperren</button>
                                ) : (
                                  <button className="btn danger" onClick={() => void lockAccount(user.id)}>Sperren</button>
                                )}
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {selectedUser && hasPermission('user.read') && (
            <div className="card section-gap">
              <div className="page-header no-margin">
                <div>
                  <h3>Benutzerdetails: {selectedUser.username}</h3>
                  <div className="muted small">Sitzungsübersicht, Rechte und Audit-Verlauf.</div>
                </div>
                {canManageUsers && (
                  <div className="table-actions">
                    <button className="btn" onClick={() => void resetPassword(selectedUser.id)}>Passwort-Reset</button>
                    {selectedUser.locked_until && new Date(selectedUser.locked_until).getTime() > Date.now() ? (
                      <button className="btn primary" onClick={() => void unlockAccount(selectedUser.id)}>Entsperren</button>
                    ) : (
                      <button className="btn danger" onClick={() => void lockAccount(selectedUser.id)}>Sperren</button>
                    )}
                  </div>
                )}
              </div>

              {adminResetToken && (
                <div className="card section-gap">
                  <div className="muted small">Einmaliger Reset-Token für die sichere Weitergabe an den Benutzer.</div>
                  <div className="stack">
                    <div className="pill">{adminResetToken}</div>
                  </div>
                </div>
              )}

              <div className="section-gap">
                <div className="muted small">{renderStatusPills(selectedUser)}</div>
                <div className="muted small mt8">Letzte Aktivität: {formatDate(selectedUser.last_activity_at)}</div>
                <div className="muted small">Lock: {selectedUser.locked_until ? formatDate(selectedUser.locked_until) : 'Nicht gesperrt'}</div>
                <div className="section-gap">{renderPermissionPills(selectedUser.permissions)}</div>
              </div>

              {detailErr && <div className="error">{detailErr}</div>}

              <div className="section-gap">
                <h4>Sitzungsübersicht</h4>
                {userSessionsQuery.isFetching && <ListSkeleton rows={3} />}
                {!userSessionsQuery.isFetching && !userSessions.length && <EmptyState title="Keine Sessions" message="Für diesen Benutzer sind keine Sessions vorhanden." />}
                {!!userSessions.length && (
                  <table>
                    <caption className="sr-only">Sitzungsübersicht des Benutzers</caption>
                    <thead>
                      <tr>
                        <th scope="col">Gerät</th>
                        <th scope="col">Status</th>
                        <th scope="col">Letzte Aktivität</th>
                        <th scope="col">Ablauf</th>
                        <th scope="col">MFA</th>
                        <th scope="col">IP</th>
                      </tr>
                    </thead>
                    <tbody>
                      {userSessions.map(session => (
                        <tr key={session.id}>
                          <td>{session.device_label || 'Unbekannt'}{session.is_current ? ' (aktuell)' : ''}</td>
                          <td><span className="pill">{formatSessionStatus(session)}</span>{session.revoked_reason ? <div className="muted small">{session.revoked_reason}</div> : null}</td>
                          <td>{formatDate(session.last_activity_at)}</td>
                          <td>{formatDate(session.expires_at)}</td>
                          <td>{session.mfa_verified ? 'Ja' : 'Nein'}</td>
                          <td>{session.ip_address || '–'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div className="section-gap">
                <h4>Rollen- und Rechte-Audit</h4>
                {roleAuditQuery.isFetching && <ListSkeleton rows={3} />}
                {!roleAudits.length && !roleAuditQuery.isFetching && <EmptyState title="Keine Änderungen" message="Für diesen Benutzer liegen keine Rollen- oder Rechteänderungen vor." />}
                {!!roleAudits.length && (
                  <table>
                    <caption className="sr-only">Audit-Verlauf zu Rollen- und Rechteänderungen</caption>
                    <thead>
                      <tr>
                        <th scope="col">Zeit</th>
                        <th scope="col">Aktion</th>
                        <th scope="col">Ausgeführt von</th>
                        <th scope="col">Von</th>
                        <th scope="col">Nach</th>
                      </tr>
                    </thead>
                    <tbody>
                      {roleAudits.map(entry => (
                        <tr key={entry.id}>
                          <td>{formatDate(entry.created_at)}</td>
                          <td><span className="pill">{entry.action}</span></td>
                          <td>{entry.actor_name || 'system'}</td>
                          <td>{entry.before?.role ? String(entry.before.role) : '–'}</td>
                          <td>{entry.after?.role ? String(entry.after.role) : '–'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}

          {hasPermission('user.approve_registration') && <div className="card section-gap">
            <div className="page-header no-margin">
              <div>
                <h3>Registrierungsanfragen</h3>
                <div className="muted small">Neue Registrierungen freigeben oder mit Begründung ablehnen.</div>
              </div>
              <span className="pill">Offen: {requests.length}</span>
            </div>
            {!requests.length && <EmptyState title="Keine offenen Anfragen" message="Derzeit liegen keine offenen Registrierungsanfragen vor." />}
            {!!requests.length && (
              <table>
                <caption className="sr-only">Offene Registrierungsanfragen</caption>
                <thead>
                  <tr>
                    <th scope="col">Username</th>
                    <th scope="col">Eingang</th>
                    <th scope="col">Status</th>
                    <th scope="col">Begründung</th>
                    <th scope="col">Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {requests.map(r => (
                    <tr key={r.id}>
                      <td>
                        <div>{r.username}</div>
                        <div className="muted small">Review-Historie sichtbar unten</div>
                      </td>
                      <td>{formatDate(r.reviewed_at || null)}</td>
                      <td><span className="pill">{r.status}</span></td>
                      <td>
                        <textarea
                          rows={2}
                          className="w100"
                          placeholder="Begründung für eine Ablehnung"
                          value={rejectionReasons[r.id] || ''}
                          onChange={event => setRejectionReasons(prev => ({ ...prev, [r.id]: event.target.value }))}
                        />
                      </td>
                      <td>
                        <div className="table-actions">
                          <button className="btn primary" onClick={() => decide(r.id, 'approve')}>Freigeben</button>
                          <button
                            className="btn danger"
                            onClick={() => decide(r.id, 'reject')}
                            disabled={!rejectionReasons[r.id]?.trim()}
                          >
                            Ablehnen
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>}

          {hasPermission('user.approve_registration') && (
            <div className="card section-gap">
              <div className="page-header no-margin">
                <div>
                  <h3>Freigabehistorie</h3>
                  <div className="muted small">Genehmigte und abgelehnte Registrierungen mit Reviewer und Grund.</div>
                </div>
                <span className="pill">Einträge: {requestHistory.length}</span>
              </div>
              {!requestHistory.length && <EmptyState title="Keine Historie" message="Es liegen noch keine freigegebenen oder abgelehnten Registrierungen vor." />}
              {!!requestHistory.length && (
                <table>
                  <caption className="sr-only">Historie der Registrierungsfreigaben</caption>
                  <thead>
                    <tr>
                      <th scope="col">Username</th>
                      <th scope="col">Status</th>
                      <th scope="col">Reviewer</th>
                      <th scope="col">Zeitpunkt</th>
                      <th scope="col">Begründung</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requestHistory.map(item => (
                      <tr key={item.id}>
                        <td>{item.username}</td>
                        <td><span className="pill">{item.status}</span></td>
                        <td>{item.reviewed_by_username || '–'}</td>
                        <td>{formatDate(item.reviewed_at)}</td>
                        <td>{item.rejection_reason || '–'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
