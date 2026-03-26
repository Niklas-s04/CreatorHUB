import React, { useMemo, useState } from 'react'
import { getErrorMessage } from '../../../shared/lib/errors'
import { useAuthz } from '../../../shared/hooks/useAuthz'
import { EmptyState } from '../../../shared/ui/states/EmptyState'
import { ErrorState } from '../../../shared/ui/states/ErrorState'
import { ListSkeleton } from '../../../shared/ui/states/ListSkeleton'
import { useToast } from '../../../shared/ui/toast/ToastProvider'
import {
  useDecideRegistrationRequestMutation,
  usePendingRegistrationRequestsQuery,
  useUsersQuery,
} from '../../../shared/api/queries/admin'

export default function AdminPage() {
  const toast = useToast()
  const { me, hasPermission, loading: authzLoading, error: authzError, reload: reloadAuthz } = useAuthz()
  const [err, setErr] = useState<string | null>(null)

  const canApprove = hasPermission('user.approve_registration')
  const canReadUsers = hasPermission('user.read')

  const requestsQuery = usePendingRegistrationRequestsQuery(!authzLoading && canApprove)
  const usersQuery = useUsersQuery(!authzLoading && canReadUsers)
  const decideMutation = useDecideRegistrationRequestMutation()

  const busy = authzLoading || requestsQuery.isFetching || usersQuery.isFetching || decideMutation.isPending
  const queryErr = useMemo(() => {
    if (requestsQuery.error) return getErrorMessage(requestsQuery.error)
    if (usersQuery.error) return getErrorMessage(usersQuery.error)
    return null
  }, [requestsQuery.error, usersQuery.error])

  const requests = canApprove ? (requestsQuery.data ?? []) : []
  const users = canReadUsers ? (usersQuery.data ?? []) : []

  async function decide(id: string, action: 'approve' | 'reject') {
    setErr(null)
    try {
      await decideMutation.mutateAsync({ id, action })
      toast.success(`Anfrage wurde ${action === 'approve' ? 'freigegeben' : 'abgelehnt'}`)
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErr(message)
      toast.error(message)
    }
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
          onClick={async () => {
            await reloadAuthz()
            await Promise.all([requestsQuery.refetch(), usersQuery.refetch()])
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
            void Promise.all([requestsQuery.refetch(), usersQuery.refetch()])
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
          {hasPermission('user.read') && <div className="card section-gap">
            <h3>Benutzer</h3>
            {!users.length && <EmptyState title="Keine Benutzer" message="Es sind aktuell keine Benutzereinträge verfügbar." />}
            {!!users.length && (
              <table>
                <caption className="sr-only">Benutzerübersicht</caption>
                <thead>
                  <tr>
                    <th scope="col">Username</th>
                    <th scope="col">Rolle</th>
                    <th scope="col">MFA</th>
                    <th scope="col">Aktive Sessions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <tr key={u.id} id={`user-${u.id}`}>
                      <td>{u.username}</td>
                      <td><span className="pill">{u.role}</span></td>
                      <td>{u.mfa_enabled ? 'Aktiv' : 'Inaktiv'}</td>
                      <td>{u.active_sessions}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>}

          {hasPermission('user.approve_registration') && <div className="card section-gap">
            <h3>Registrierungsanfragen</h3>
            {!requests.length && <EmptyState title="Keine offenen Anfragen" message="Derzeit liegen keine offenen Registrierungsanfragen vor." />}
            {!!requests.length && (
              <table>
                <caption className="sr-only">Offene Registrierungsanfragen</caption>
                <thead>
                  <tr>
                    <th scope="col">Username</th>
                    <th scope="col">Status</th>
                    <th scope="col">Aktionen</th>
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
          </div>}
        </>
      )}
    </div>
  )
}
