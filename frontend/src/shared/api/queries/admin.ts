import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch, getUsers, type RegistrationRequest, type UserSummary } from '../../../api'
import { queryKeys } from '../queryKeys'

export function usePendingRegistrationRequestsQuery(enabled: boolean) {
  return useQuery<RegistrationRequest[]>({
    queryKey: queryKeys.admin.registrationRequests('pending'),
    enabled,
    staleTime: 15_000,
    queryFn: async () => {
      return apiFetch<RegistrationRequest[]>('/auth/registration-requests?status_filter=pending')
    },
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

export function useDecideRegistrationRequestMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, action }: { id: string; action: 'approve' | 'reject' }) => {
      await apiFetch(`/auth/registration-requests/${id}/${action}`, { method: 'POST' })
    },
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['admin', 'registrationRequests'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.auth.users() }),
      ])
    },
  })
}
