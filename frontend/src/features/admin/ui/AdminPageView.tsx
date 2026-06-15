import React, { useEffect, useMemo, useState } from 'react'
import { getErrorMessage } from '../../../shared/lib/errors'
import { useAuthz } from '../../../shared/hooks/useAuthz'
import { useI18n } from '../../../shared/i18n/i18n'
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
  const { language } = useI18n()
  const {
    me,
    hasPermission,
    loading: authzLoading,
    error: authzError,
    reload: reloadAuthz,
  } = useAuthz()
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
  const selectedUser: UserSummary | null = selectedUserId
    ? (users.find((user) => user.id === selectedUserId) ?? null)
    : null
  const userSessions: AdminSession[] = userSessionsQuery.data ?? []
  const roleAudits: RoleAuditEntry[] = (roleAuditQuery.data ?? []) as RoleAuditEntry[]
  const isEnglish = language === 'en'

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
      toast.success(
        isEnglish
          ? `Request was ${action === 'approve' ? 'approved' : 'rejected'}`
          : `Anfrage wurde ${action === 'approve' ? 'freigegeben' : 'abgelehnt'}`
      )
      if (action === 'reject') {
        setRejectionReasons((prev) => ({ ...prev, [id]: '' }))
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
    await Promise.all([
      requestsQuery.refetch(),
      requestHistoryQuery.refetch(),
      usersQuery.refetch(),
      ...detailRefetches,
    ])
  }

  async function resetPassword(userId: string) {
    setErr(null)
    setAdminResetToken(null)
    try {
      const response = await adminActions.passwordReset.mutateAsync({ userId })
      setAdminResetToken(response.reset_token)
      toast.success(isEnglish ? 'Password reset triggered' : 'Passwort-Reset ausgelöst')
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
      toast.success(isEnglish ? 'User locked' : 'Benutzer gesperrt')
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
      toast.success(isEnglish ? 'User unlocked' : 'Benutzer entsperrt')
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

  function formatSessionStatus(session: {
    revoked_at: string | null
    expires_at: string
    is_current: boolean
  }) {
    if (session.revoked_at) return isEnglish ? 'Revoked' : 'Widerrufen'
    if (new Date(session.expires_at).getTime() <= Date.now())
      return isEnglish ? 'Expired' : 'Abgelaufen'
    if (session.is_current) return isEnglish ? 'Current' : 'Aktuell'
    return isEnglish ? 'Active' : 'Aktiv'
  }

  function renderPermissionPills(permissions: string[], limit = permissions.length) {
    const visible = permissions.slice(0, limit)
    const hidden = permissions.length - visible.length
    return (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
        {visible.map((permission) => (
          <span key={permission} className="pill">
            {permission}
          </span>
        ))}
        {hidden > 0 && <span className="pill">+{hidden}</span>}
      </div>
    )
  }

  function renderStatusPills(user: NonNullable<typeof selectedUser> | (typeof users)[number]) {
    const pills: Array<{ label: string; tone?: 'primary' | 'danger' }> = []
    if (!user.is_active) pills.push({ label: isEnglish ? 'Inactive' : 'Inaktiv', tone: 'danger' })
    else if (user.locked_until && new Date(user.locked_until).getTime() > Date.now()) {
      pills.push({
        label: isEnglish
          ? `Locked until ${formatDate(user.locked_until)}`
          : `Gesperrt bis ${formatDate(user.locked_until)}`,
        tone: 'danger',
      })
    } else {
      pills.push({ label: isEnglish ? 'Active' : 'Aktiv', tone: 'primary' })
    }
    if (user.needs_password_setup)
      pills.push({ label: isEnglish ? 'Password reset pending' : 'Passwort-Reset offen' })
    if (user.mfa_enabled) pills.push({ label: isEnglish ? 'MFA enabled' : 'MFA aktiv' })
    else pills.push({ label: isEnglish ? 'MFA disabled' : 'MFA inaktiv' })

    return (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
        {pills.map((pill) => (
          <span key={pill.label} className={`pill ${pill.tone ? pill.tone : ''}`.trim()}>
            {pill.label}
          </span>
        ))}
      </div>
    )
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h2 className="page-title">{isEnglish ? 'Administration' : 'Administration'}</h2>
          <div className="page-subtitle">
            {isEnglish
              ? 'Manage registration requests centrally.'
              : 'Verwalte Registrierungsanfragen zentral.'}
          </div>
        </div>
        <button
          className="btn"
          onClick={() => {
            void refreshAll()
          }}
          disabled={busy || authzLoading}
        >
          {busy || authzLoading ? '...' : isEnglish ? 'Refresh' : 'Aktualisieren'}
        </button>
      </div>

      {authzError && <div className="error">{authzError}</div>}
      {queryErr && (
        <ErrorState
          title={
            isEnglish
              ? 'Admin data could not be loaded'
              : 'Admin-Daten konnten nicht geladen werden'
          }
          message={queryErr}
          onRetry={() => {
            void Promise.all([
              requestsQuery.refetch(),
              requestHistoryQuery.refetch(),
              usersQuery.refetch(),
            ])
          }}
        />
      )}
      {err && <div className="error">{err}</div>}

      {busy && !requests.length && !users.length && <ListSkeleton rows={4} />}

      {me && !hasPermission('user.approve_registration') && !hasPermission('user.read') && (
        <div className="card">
          {isEnglish
            ? 'Only admins can handle registration requests.'
            : 'Nur Admin kann Registrierungsanfragen bearbeiten.'}
        </div>
      )}

      {me && (
        <>
          {hasPermission('user.read') && (
            <div className="card section-gap">
              <div className="page-header no-margin">
                <div>
                  <h3>{isEnglish ? 'Users' : 'Benutzer'}</h3>
                  <div className="muted small">
                    {isEnglish
                      ? 'Status, permissions, MFA and activity at a glance.'
                      : 'Status, Rechte, MFA und Aktivität auf einen Blick.'}
                  </div>
                </div>
                {canManageUsers && (
                  <span className="pill">
                    {isEnglish ? 'Management enabled' : 'Verwaltung aktiv'}
                  </span>
                )}
              </div>
              {!users.length && (
                <EmptyState
                  title={isEnglish ? 'No users' : 'Keine Benutzer'}
                  message={
                    isEnglish
                      ? 'No user records are available right now.'
                      : 'Es sind aktuell keine Benutzereinträge verfügbar.'
                  }
                />
              )}
              {!!users.length && (
                <table>
                  <caption className="sr-only">
                    {isEnglish ? 'User overview' : 'Benutzerübersicht'}
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">{isEnglish ? 'User' : 'Benutzer'}</th>
                      <th scope="col">{isEnglish ? 'Status' : 'Status'}</th>
                      <th scope="col">{isEnglish ? 'Role / permissions' : 'Rolle / Rechte'}</th>
                      <th scope="col">{isEnglish ? 'MFA' : 'MFA'}</th>
                      <th scope="col">{isEnglish ? 'Last activity' : 'Letzte Aktivität'}</th>
                      <th scope="col">{isEnglish ? 'Sessions' : 'Sessions'}</th>
                      <th scope="col">{isEnglish ? 'Actions' : 'Aktionen'}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((user) => (
                      <tr key={user.id} id={`user-${user.id}`}>
                        <td>
                          <button
                            type="button"
                            className="btn"
                            onClick={() => selectUser(user.id)}
                            aria-label={
                              isEnglish
                                ? `Show details for ${user.username}`
                                : `Details für ${user.username} anzeigen`
                            }
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
                        <td>
                          {user.mfa_enabled
                            ? isEnglish
                              ? 'Active'
                              : 'Aktiv'
                            : isEnglish
                              ? 'Inactive'
                              : 'Inaktiv'}
                        </td>
                        <td>{formatDate(user.last_activity_at)}</td>
                        <td>{user.active_sessions}</td>
                        <td>
                          <div className="table-actions">
                            <button className="btn" onClick={() => selectUser(user.id)}>
                              {isEnglish ? 'Sessions' : 'Sessions'}
                            </button>
                            {canManageUsers && (
                              <>
                                <button className="btn" onClick={() => void resetPassword(user.id)}>
                                  {isEnglish ? 'Password reset' : 'Passwort-Reset'}
                                </button>
                                {user.locked_until &&
                                new Date(user.locked_until).getTime() > Date.now() ? (
                                  <button
                                    className="btn primary"
                                    onClick={() => void unlockAccount(user.id)}
                                  >
                                    {isEnglish ? 'Unlock' : 'Entsperren'}
                                  </button>
                                ) : (
                                  <button
                                    className="btn danger"
                                    onClick={() => void lockAccount(user.id)}
                                  >
                                    {isEnglish ? 'Lock' : 'Sperren'}
                                  </button>
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
                  <h3>
                    {isEnglish ? 'User details' : 'Benutzerdetails'}: {selectedUser.username}
                  </h3>
                  <div className="muted small">
                    {isEnglish
                      ? 'Session overview, permissions and audit history.'
                      : 'Sitzungsübersicht, Rechte und Audit-Verlauf.'}
                  </div>
                </div>
                {canManageUsers && (
                  <div className="table-actions">
                    <button className="btn" onClick={() => void resetPassword(selectedUser.id)}>
                      {isEnglish ? 'Password reset' : 'Passwort-Reset'}
                    </button>
                    {selectedUser.locked_until &&
                    new Date(selectedUser.locked_until).getTime() > Date.now() ? (
                      <button
                        className="btn primary"
                        onClick={() => void unlockAccount(selectedUser.id)}
                      >
                        {isEnglish ? 'Unlock' : 'Entsperren'}
                      </button>
                    ) : (
                      <button
                        className="btn danger"
                        onClick={() => void lockAccount(selectedUser.id)}
                      >
                        {isEnglish ? 'Lock' : 'Sperren'}
                      </button>
                    )}
                  </div>
                )}
              </div>

              {adminResetToken && (
                <div className="card section-gap">
                  <div className="muted small">
                    {isEnglish
                      ? 'One-time reset token for secure handoff to the user.'
                      : 'Einmaliger Reset-Token für die sichere Weitergabe an den Benutzer.'}
                  </div>
                  <div className="stack">
                    <div className="pill">{adminResetToken}</div>
                  </div>
                </div>
              )}

              <div className="section-gap">
                <div className="muted small">{renderStatusPills(selectedUser)}</div>
                <div className="muted small mt8">
                  {isEnglish ? 'Last activity' : 'Letzte Aktivität'}:{' '}
                  {formatDate(selectedUser.last_activity_at)}
                </div>
                <div className="muted small">
                  {isEnglish ? 'Lock' : 'Sperre'}:{' '}
                  {selectedUser.locked_until
                    ? formatDate(selectedUser.locked_until)
                    : isEnglish
                      ? 'Not locked'
                      : 'Nicht gesperrt'}
                </div>
                <div className="section-gap">{renderPermissionPills(selectedUser.permissions)}</div>
              </div>

              {detailErr && <div className="error">{detailErr}</div>}

              <div className="section-gap">
                <h4>{isEnglish ? 'Session overview' : 'Sitzungsübersicht'}</h4>
                {userSessionsQuery.isFetching && <ListSkeleton rows={3} />}
                {!userSessionsQuery.isFetching && !userSessions.length && (
                  <EmptyState
                    title={isEnglish ? 'No sessions' : 'Keine Sessions'}
                    message={
                      isEnglish
                        ? 'No sessions exist for this user.'
                        : 'Für diesen Benutzer sind keine Sessions vorhanden.'
                    }
                  />
                )}
                {!!userSessions.length && (
                  <table>
                    <caption className="sr-only">
                      {isEnglish ? 'User session overview' : 'Sitzungsübersicht des Benutzers'}
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">{isEnglish ? 'Device' : 'Gerät'}</th>
                        <th scope="col">{isEnglish ? 'Status' : 'Status'}</th>
                        <th scope="col">{isEnglish ? 'Last activity' : 'Letzte Aktivität'}</th>
                        <th scope="col">{isEnglish ? 'Expiry' : 'Ablauf'}</th>
                        <th scope="col">{isEnglish ? 'MFA' : 'MFA'}</th>
                        <th scope="col">IP</th>
                      </tr>
                    </thead>
                    <tbody>
                      {userSessions.map((session) => (
                        <tr key={session.id}>
                          <td>
                            {session.device_label || (isEnglish ? 'Unknown' : 'Unbekannt')}
                            {session.is_current ? (isEnglish ? ' (current)' : ' (aktuell)') : ''}
                          </td>
                          <td>
                            <span className="pill">{formatSessionStatus(session)}</span>
                            {session.revoked_reason ? (
                              <div className="muted small">{session.revoked_reason}</div>
                            ) : null}
                          </td>
                          <td>{formatDate(session.last_activity_at)}</td>
                          <td>{formatDate(session.expires_at)}</td>
                          <td>
                            {session.mfa_verified
                              ? isEnglish
                                ? 'Yes'
                                : 'Ja'
                              : isEnglish
                                ? 'No'
                                : 'Nein'}
                          </td>
                          <td>{session.ip_address || '–'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div className="section-gap">
                <h4>{isEnglish ? 'Role and permission audit' : 'Rollen- und Rechte-Audit'}</h4>
                {roleAuditQuery.isFetching && <ListSkeleton rows={3} />}
                {!roleAudits.length && !roleAuditQuery.isFetching && (
                  <EmptyState
                    title={isEnglish ? 'No changes' : 'Keine Änderungen'}
                    message={
                      isEnglish
                        ? 'There are no role or permission changes for this user.'
                        : 'Für diesen Benutzer liegen keine Rollen- oder Rechteänderungen vor.'
                    }
                  />
                )}
                {!!roleAudits.length && (
                  <table>
                    <caption className="sr-only">
                      {isEnglish
                        ? 'Audit history for role and permission changes'
                        : 'Audit-Verlauf zu Rollen- und Rechteänderungen'}
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">{isEnglish ? 'Time' : 'Zeit'}</th>
                        <th scope="col">{isEnglish ? 'Action' : 'Aktion'}</th>
                        <th scope="col">{isEnglish ? 'Performed by' : 'Ausgeführt von'}</th>
                        <th scope="col">{isEnglish ? 'From' : 'Von'}</th>
                        <th scope="col">{isEnglish ? 'To' : 'Nach'}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {roleAudits.map((entry) => (
                        <tr key={entry.id}>
                          <td>{formatDate(entry.created_at)}</td>
                          <td>
                            <span className="pill">{entry.action}</span>
                          </td>
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

          {hasPermission('user.approve_registration') && (
            <div className="card section-gap">
              <div className="page-header no-margin">
                <div>
                  <h3>{isEnglish ? 'Registration requests' : 'Registrierungsanfragen'}</h3>
                  <div className="muted small">
                    {isEnglish
                      ? 'Approve new registrations or reject them with a reason.'
                      : 'Neue Registrierungen freigeben oder mit Begründung ablehnen.'}
                  </div>
                </div>
                <span className="pill">
                  {isEnglish ? 'Open' : 'Offen'}: {requests.length}
                </span>
              </div>
              {!requests.length && (
                <EmptyState
                  title={isEnglish ? 'No open requests' : 'Keine offenen Anfragen'}
                  message={
                    isEnglish
                      ? 'There are no open registration requests right now.'
                      : 'Derzeit liegen keine offenen Registrierungsanfragen vor.'
                  }
                />
              )}
              {!!requests.length && (
                <table>
                  <caption className="sr-only">
                    {isEnglish ? 'Open registration requests' : 'Offene Registrierungsanfragen'}
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">{isEnglish ? 'Username' : 'Username'}</th>
                      <th scope="col">{isEnglish ? 'Submitted' : 'Eingang'}</th>
                      <th scope="col">{isEnglish ? 'Status' : 'Status'}</th>
                      <th scope="col">{isEnglish ? 'Reason' : 'Begründung'}</th>
                      <th scope="col">{isEnglish ? 'Actions' : 'Aktionen'}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requests.map((r) => (
                      <tr key={r.id}>
                        <td>
                          <div>{r.username}</div>
                          <div className="muted small">
                            {isEnglish
                              ? 'Review history shown below'
                              : 'Review-Historie sichtbar unten'}
                          </div>
                        </td>
                        <td>{formatDate(r.reviewed_at || null)}</td>
                        <td>
                          <span className="pill">{r.status}</span>
                        </td>
                        <td>
                          <textarea
                            rows={2}
                            className="w100"
                            placeholder={
                              isEnglish ? 'Reason for rejection' : 'Begründung für eine Ablehnung'
                            }
                            value={rejectionReasons[r.id] || ''}
                            onChange={(event) =>
                              setRejectionReasons((prev) => ({
                                ...prev,
                                [r.id]: event.target.value,
                              }))
                            }
                          />
                        </td>
                        <td>
                          <div className="table-actions">
                            <button className="btn primary" onClick={() => decide(r.id, 'approve')}>
                              {isEnglish ? 'Approve' : 'Freigeben'}
                            </button>
                            <button
                              className="btn danger"
                              onClick={() => decide(r.id, 'reject')}
                              disabled={!rejectionReasons[r.id]?.trim()}
                            >
                              {isEnglish ? 'Reject' : 'Ablehnen'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {hasPermission('user.approve_registration') && (
            <div className="card section-gap">
              <div className="page-header no-margin">
                <div>
                  <h3>{isEnglish ? 'Approval history' : 'Freigabehistorie'}</h3>
                  <div className="muted small">
                    {isEnglish
                      ? 'Approved and rejected registrations with reviewer and reason.'
                      : 'Genehmigte und abgelehnte Registrierungen mit Reviewer und Grund.'}
                  </div>
                </div>
                <span className="pill">
                  {isEnglish ? 'Entries' : 'Einträge'}: {requestHistory.length}
                </span>
              </div>
              {!requestHistory.length && (
                <EmptyState
                  title={isEnglish ? 'No history' : 'Keine Historie'}
                  message={
                    isEnglish
                      ? 'There are no approved or rejected registrations yet.'
                      : 'Es liegen noch keine freigegebenen oder abgelehnten Registrierungen vor.'
                  }
                />
              )}
              {!!requestHistory.length && (
                <table>
                  <caption className="sr-only">
                    {isEnglish
                      ? 'Registration approval history'
                      : 'Historie der Registrierungsfreigaben'}
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">{isEnglish ? 'Username' : 'Username'}</th>
                      <th scope="col">{isEnglish ? 'Status' : 'Status'}</th>
                      <th scope="col">{isEnglish ? 'Reviewer' : 'Reviewer'}</th>
                      <th scope="col">{isEnglish ? 'Time' : 'Zeitpunkt'}</th>
                      <th scope="col">{isEnglish ? 'Reason' : 'Begründung'}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requestHistory.map((item) => (
                      <tr key={item.id}>
                        <td>{item.username}</td>
                        <td>
                          <span className="pill">{item.status}</span>
                        </td>
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
