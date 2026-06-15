import { useQuery } from '@tanstack/react-query'
import { useCallback, useMemo } from 'react'
import { getMe, type Me, type Permission } from '../../api'
import { getErrorMessage } from '../lib/errors'
import { queryKeys } from '../api/queryKeys'

type UseAuthzResult = {
  me: Me | null
  loading: boolean
  error: string | null
  hasPermission: (permission: Permission) => boolean
  reload: () => Promise<void>
}

export function useAuthz(): UseAuthzResult {
  const meQuery = useQuery({
    queryKey: queryKeys.auth.me(),
    queryFn: getMe,
    staleTime: 60_000,
    retry: false,
  })
  const { refetch } = meQuery

  const me = meQuery.data ?? null
  const permissionSet = useMemo(() => new Set(me?.permissions || []), [me])
  const hasPermission = useCallback(
    (permission: Permission) => permissionSet.has(permission),
    [permissionSet]
  )
  const reload = useCallback(async () => {
    await refetch()
  }, [refetch])

  return {
    me,
    loading: meQuery.isLoading || meQuery.isFetching,
    error: meQuery.error ? getErrorMessage(meQuery.error) : null,
    hasPermission,
    reload,
  }
}
