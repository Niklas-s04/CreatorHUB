import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  approveRegistrationRequest,
  apiFetch,
  getRegistrationRequests,
  getUserSessions,
  getUsers,
  lockUser,
  rejectRegistrationRequest,
  requestAdminPasswordReset,
  unlockUser,
  type AdminSession,
  type RegistrationRequest,
  type UserSummary,
} from '../../../api'
import { queryKeys } from '../queryKeys'

type AuditEntry = {
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

type PageLike<T> = { items: T[] }

export function usePendingRegistrationRequestsQuery(enabled: boolean) {
  return useQuery<RegistrationRequest[]>({
    queryKey: queryKeys.admin.registrationRequests('pending'),
    enabled,
    staleTime: 15_000,
    queryFn: async () => {
      return getRegistrationRequests('pending')
    },
  })
}

export function useRegistrationRequestHistoryQuery(enabled: boolean) {
  return useQuery<RegistrationRequest[]>({
    queryKey: queryKeys.admin.registrationRequestsAll(),
    enabled,
    staleTime: 15_000,
    queryFn: async () => getRegistrationRequests(),
  })
}

export function useUsersQuery(enabled: boolean) {
  return useQuery<UserSummary[]>({
    queryKey: queryKeys.auth.users(),
    enabled,
    staleTime: 20_000,
    queryFn: async () => getUsers(),
  })
}

export function useAdminUserSessionsQuery(userId: string | null, enabled: boolean) {
  return useQuery<AdminSession[]>({
    queryKey: userId ? queryKeys.admin.userSessions(userId) : ['admin', 'userSessions', 'none'],
    enabled: enabled && Boolean(userId),
    staleTime: 10_000,
    queryFn: async () => getUserSessions(userId as string),
  })
}

export function useAdminRoleAuditQuery(userId: string | null, enabled: boolean) {
  return useQuery<AuditEntry[]>({
    queryKey: userId ? ['admin', 'roleAudit', userId] : ['admin', 'roleAudit', 'none'],
    enabled: enabled && Boolean(userId),
    staleTime: 10_000,
    queryFn: async () => {
      const response = await apiFetch<PageLike<AuditEntry> & { meta?: { total?: number } }>(
        `/audit?entity_type=user&action=user.role_or_status.update&entity_id=${encodeURIComponent(String(userId))}&limit=5&offset=0&sort_by=created_at&sort_order=desc`
      )
      return response.items ?? []
    },
  })
}

export function useDecideRegistrationRequestMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({
      id,
      action,
      reason,
    }: {
      id: string
      action: 'approve' | 'reject'
      reason?: string
    }) => {
      if (action === 'approve') {
        await approveRegistrationRequest(id)
      } else {
        await rejectRegistrationRequest(id, reason || '')
      }
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['admin', 'registrationRequests'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.admin.registrationRequestsAll() }),
        queryClient.invalidateQueries({ queryKey: queryKeys.auth.users() }),
      ])
    },
  })
}

export function useAdminUserActionsMutation() {
  const queryClient = useQueryClient()

  const invalidateUserData = async (userId: string) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.auth.users() }),
      queryClient.invalidateQueries({ queryKey: queryKeys.admin.userSessions(userId) }),
      queryClient.invalidateQueries({ queryKey: ['admin', 'roleAudit', userId] }),
    ])
  }

  const passwordReset = useMutation({
    mutationFn: async ({ userId }: { userId: string }) => requestAdminPasswordReset(userId),
    onSuccess: async (_, variables) => {
      await invalidateUserData(variables.userId)
    },
  })

  const lock = useMutation({
    mutationFn: async ({ userId, minutes }: { userId: string; minutes?: number }) =>
      lockUser(userId, minutes),
    onSuccess: async (_, variables) => {
      await invalidateUserData(variables.userId)
    },
  })

  const unlock = useMutation({
    mutationFn: async ({ userId }: { userId: string }) => unlockUser(userId),
    onSuccess: async (_, variables) => {
      await invalidateUserData(variables.userId)
    },
  })

  return { passwordReset, lock, unlock }
}
