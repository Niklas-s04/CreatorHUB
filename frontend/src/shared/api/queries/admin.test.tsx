import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import {
  useAdminRoleAuditQuery,
  useAdminUserActionsMutation,
  useAdminUserSessionsQuery,
  useCreateUserMutation,
  useDecideRegistrationRequestMutation,
  usePendingRegistrationRequestsQuery,
  useRegistrationRequestHistoryQuery,
  useUsersQuery,
} from './admin'

vi.mock('../../../api', () => ({
  approveRegistrationRequest: vi.fn(),
  apiFetch: vi.fn(),
  createUser: vi.fn(),
  getRegistrationRequests: vi.fn(),
  getUserSessions: vi.fn(),
  getUsers: vi.fn(),
  lockUser: vi.fn(),
  rejectRegistrationRequest: vi.fn(),
  requestAdminPasswordReset: vi.fn(),
  unlockUser: vi.fn(),
}))

import {
  approveRegistrationRequest,
  apiFetch,
  createUser,
  getRegistrationRequests,
  getUserSessions,
  getUsers,
  lockUser,
  rejectRegistrationRequest,
  requestAdminPasswordReset,
  unlockUser,
} from '../../../api'

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

describe('admin queries and mutations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads admin collections and audit history', async () => {
    const queryClient = createQueryClient()
    ;(getRegistrationRequests as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce([
        {
          id: 'r1',
          username: 'new-user',
          status: 'pending',
          reviewed_at: null,
          reviewed_by_user_id: null,
          reviewed_by_username: null,
          rejection_reason: null,
        },
      ])
      .mockResolvedValueOnce([
        {
          id: 'r2',
          username: 'done-user',
          status: 'approved',
          reviewed_at: '2024-01-01T00:00:00Z',
          reviewed_by_user_id: 'a1',
          reviewed_by_username: 'admin',
          rejection_reason: null,
        },
      ])
    ;(getUsers as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        id: 'u1',
        username: 'alice',
        role: 'editor',
        is_active: true,
        needs_password_setup: false,
        mfa_enabled: false,
        locked_until: null,
        last_activity_at: null,
        active_sessions: 2,
        permissions: ['content.read'],
      },
    ])
    ;(getUserSessions as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        id: 's1',
        created_at: '2024-01-01T00:00:00Z',
        last_activity_at: '2024-01-01T00:00:00Z',
        expires_at: '2024-01-02T00:00:00Z',
        idle_expires_at: '2024-01-01T01:00:00Z',
        ip_address: null,
        device_label: null,
        user_agent: null,
        mfa_verified: true,
        mfa_step_up_expires_at: '2024-01-01T00:05:00Z',
        is_current: false,
        revoked_at: null,
        revoked_reason: null,
      },
    ])
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [
        {
          id: 'a1',
          action: 'user.role_or_status.update',
          entity_type: 'user',
          entity_id: 'u1',
          description: null,
          actor_name: 'admin',
          before: null,
          after: null,
          meta: null,
          created_at: '2024-01-01T00:00:00Z',
        },
      ],
    })

    const pending = renderHook(() => usePendingRegistrationRequestsQuery(true), {
      wrapper: createWrapper(queryClient),
    })
    const history = renderHook(() => useRegistrationRequestHistoryQuery(true), {
      wrapper: createWrapper(queryClient),
    })
    const users = renderHook(() => useUsersQuery(true), { wrapper: createWrapper(queryClient) })
    const sessions = renderHook(() => useAdminUserSessionsQuery('u1', true), {
      wrapper: createWrapper(queryClient),
    })
    const audit = renderHook(() => useAdminRoleAuditQuery('u1', true), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => expect(pending.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(history.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(users.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(sessions.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(audit.result.current.isSuccess).toBe(true))

    expect(pending.result.current.data).toHaveLength(1)
    expect(history.result.current.data).toHaveLength(1)
    expect(users.result.current.data?.[0]?.username).toBe('alice')
    expect(sessions.result.current.data?.[0]?.id).toBe('s1')
    expect(audit.result.current.data?.[0]?.action).toBe('user.role_or_status.update')
  })

  it('approves and rejects registration requests', async () => {
    const queryClient = createQueryClient()
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries')
    ;(approveRegistrationRequest as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 'r1',
    })
    ;(rejectRegistrationRequest as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 'r2',
    })

    const { result } = renderHook(() => useDecideRegistrationRequestMutation(), {
      wrapper: createWrapper(queryClient),
    })

    await act(async () => {
      await result.current.mutateAsync({ id: 'r1', action: 'approve' })
      await result.current.mutateAsync({ id: 'r2', action: 'reject', reason: 'nope' })
    })

    expect(approveRegistrationRequest).toHaveBeenCalledWith('r1')
    expect(rejectRegistrationRequest).toHaveBeenCalledWith('r2', 'nope')
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['admin', 'registrationRequests'] })
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['admin', 'registrationRequests', 'all'],
    })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['auth', 'users'] })
  })

  it('creates users and refreshes the user overview', async () => {
    const queryClient = createQueryClient()
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries')
    ;(createUser as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 'u2',
      username: 'bob',
      role: 'viewer',
      is_active: false,
      permissions: ['content.read'],
    })

    const { result } = renderHook(() => useCreateUserMutation(), {
      wrapper: createWrapper(queryClient),
    })

    await act(async () => {
      await result.current.mutateAsync({
        username: 'bob',
        password: 'NewStrong!Pass123',
        role: 'viewer',
        is_active: false,
      })
    })

    expect(createUser).toHaveBeenCalledWith({
      username: 'bob',
      password: 'NewStrong!Pass123',
      role: 'viewer',
      is_active: false,
    })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['auth', 'users'] })
  })

  it('invalidates admin user data after user actions', async () => {
    const queryClient = createQueryClient()
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries')
    ;(requestAdminPasswordReset as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true,
      reset_token: null,
    })
    ;(lockUser as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({})
    ;(unlockUser as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({})

    const { result } = renderHook(() => useAdminUserActionsMutation(), {
      wrapper: createWrapper(queryClient),
    })

    await act(async () => {
      await result.current.passwordReset.mutateAsync({ userId: 'u1' })
      await result.current.lock.mutateAsync({ userId: 'u1', minutes: 15 })
      await result.current.unlock.mutateAsync({ userId: 'u1' })
    })

    expect(requestAdminPasswordReset).toHaveBeenCalledWith('u1')
    expect(lockUser).toHaveBeenCalledWith('u1', 15)
    expect(unlockUser).toHaveBeenCalledWith('u1')
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['auth', 'users'] })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['admin', 'userSessions', 'u1'] })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['admin', 'roleAudit', 'u1'] })
  })
})
