import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import AdminPage from './AdminPageView'

const toastSuccess = vi.fn()
const toastError = vi.fn()
const createUserMutate = vi.fn()

vi.mock('../../../shared/hooks/useAuthz', () => ({
  useAuthz: () => ({
    me: {
      id: 'a1',
      username: 'admin',
      role: 'admin',
      is_active: true,
      needs_password_setup: false,
      permissions: ['user.read', 'user.manage', 'user.approve_registration'],
    },
    hasPermission: (permission: string) =>
      ['user.read', 'user.manage', 'user.approve_registration'].includes(permission),
    loading: false,
    error: null,
    reload: vi.fn(),
  }),
}))

vi.mock('../../../shared/api/queries/admin', () => ({
  usePendingRegistrationRequestsQuery: () => ({
    data: [
      {
        id: 'r1',
        username: 'new-user',
        status: 'pending',
        reviewed_at: null,
        reviewed_by_user_id: null,
        reviewed_by_username: null,
        rejection_reason: null,
      },
    ],
    error: null,
    isFetching: false,
    refetch: vi.fn(),
  }),
  useRegistrationRequestHistoryQuery: () => ({
    data: [
      {
        id: 'r2',
        username: 'old-user',
        status: 'approved',
        reviewed_at: '2024-01-01T00:00:00Z',
        reviewed_by_user_id: 'a1',
        reviewed_by_username: 'admin',
        rejection_reason: null,
      },
    ],
    error: null,
    isFetching: false,
    refetch: vi.fn(),
  }),
  useUsersQuery: () => ({
    data: [
      {
        id: 'u1',
        username: 'alice',
        role: 'editor',
        is_active: true,
        needs_password_setup: false,
        mfa_enabled: true,
        locked_until: null,
        last_activity_at: '2024-01-01T00:00:00Z',
        active_sessions: 1,
        permissions: ['content.read'],
      },
    ],
    error: null,
    isFetching: false,
    refetch: vi.fn(),
  }),
  useAdminUserSessionsQuery: () => ({
    data: [
      {
        id: 's1',
        created_at: '2024-01-01T00:00:00Z',
        last_activity_at: '2024-01-01T00:00:00Z',
        expires_at: '2024-01-02T00:00:00Z',
        idle_expires_at: '2024-01-01T01:00:00Z',
        ip_address: '127.0.0.1',
        device_label: 'Desktop',
        user_agent: null,
        mfa_verified: true,
        mfa_step_up_expires_at: '2024-01-01T00:05:00Z',
        is_current: true,
        revoked_at: null,
        revoked_reason: null,
      },
    ],
    error: null,
    isFetching: false,
    refetch: vi.fn(),
  }),
  useAdminRoleAuditQuery: () => ({
    data: [
      {
        id: 'a1',
        action: 'user.role_or_status.update',
        entity_type: 'user',
        entity_id: 'u1',
        description: null,
        actor_name: 'admin',
        before: { role: 'viewer' },
        after: { role: 'editor' },
        meta: null,
        created_at: '2024-01-01T00:00:00Z',
      },
    ],
    error: null,
    isFetching: false,
    refetch: vi.fn(),
  }),
  useDecideRegistrationRequestMutation: () => ({
    mutateAsync: vi.fn().mockResolvedValue(undefined),
    isPending: false,
  }),
  useCreateUserMutation: () => ({
    mutateAsync: createUserMutate,
    isPending: false,
  }),
  useAdminUserActionsMutation: () => ({
    passwordReset: {
      mutateAsync: vi.fn().mockResolvedValue({ reset_token: 'reset-1' }),
      isPending: false,
    },
    lock: { mutateAsync: vi.fn().mockResolvedValue(undefined), isPending: false },
    unlock: { mutateAsync: vi.fn().mockResolvedValue(undefined), isPending: false },
  }),
}))

vi.mock('../../../shared/ui/toast/ToastProvider', () => ({
  useToast: () => ({ success: toastSuccess, error: toastError }),
}))

describe('AdminPageView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    createUserMutate.mockResolvedValue({
      id: 'u2',
      username: 'bob',
      role: 'viewer',
      is_active: false,
      permissions: ['content.read'],
    })
  })

  it('renders user details, approval controls and admin actions', async () => {
    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>
    )

    expect(screen.getByText('Administration')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Benutzer' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Registrierungsanfragen' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Details für alice anzeigen' }))
    expect(await screen.findByText('Benutzerdetails: alice')).toBeInTheDocument()
    const sessionToggle = screen.getByRole('button', { name: /Sitzungsübersicht/ })
    expect(sessionToggle).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(sessionToggle)
    expect(sessionToggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Desktop (aktuell)')).toBeInTheDocument()
    expect(screen.getByText('Rollen- und Rechte-Audit')).toBeInTheDocument()

    fireEvent.change(screen.getByPlaceholderText('Begründung für eine Ablehnung'), {
      target: { value: 'missing docs' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Freigeben' }))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Anfrage wurde freigegeben'))

    fireEvent.click(screen.getAllByRole('button', { name: 'Passwort-Reset' })[0])
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Passwort-Reset ausgelöst'))

    fireEvent.click(screen.getAllByRole('button', { name: 'Sperren' })[0])
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Benutzer gesperrt'))
  })

  it('creates a user with role, password and initial status', async () => {
    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>
    )

    fireEvent.change(screen.getByLabelText('Benutzername / Name'), {
      target: { value: 'bob' },
    })
    fireEvent.change(screen.getByLabelText('Rolle'), {
      target: { value: 'viewer' },
    })
    fireEvent.change(screen.getByLabelText('Passwort'), {
      target: { value: 'NewStrong!Pass123' },
    })
    fireEvent.change(screen.getByLabelText('Passwort bestätigen'), {
      target: { value: 'NewStrong!Pass123' },
    })
    fireEvent.click(screen.getByLabelText(/Aktiv anlegen/))
    fireEvent.click(screen.getByRole('button', { name: 'Benutzer anlegen' }))

    await waitFor(() =>
      expect(createUserMutate).toHaveBeenCalledWith({
        username: 'bob',
        password: 'NewStrong!Pass123',
        role: 'viewer',
        is_active: false,
      })
    )
    expect(toastSuccess).toHaveBeenCalledWith('Benutzer bob wurde angelegt')
  })
})
