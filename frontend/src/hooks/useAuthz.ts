import { useCallback, useEffect, useMemo, useState } from 'react'
import { getMe, type Me, type Permission } from '../api'

type UseAuthzResult = {
  me: Me | null
  loading: boolean
  error: string | null
  hasPermission: (permission: Permission) => boolean
  reload: () => Promise<void>
}

export function useAuthz(): UseAuthzResult {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getMe()
      setMe(data)
    } catch (e: any) {
      setError(e.message || String(e))
      setMe(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const permissionSet = useMemo(() => new Set(me?.permissions || []), [me])
  const hasPermission = useCallback(
    (permission: Permission) => permissionSet.has(permission),
    [permissionSet]
  )

  return {
    me,
    loading,
    error,
    hasPermission,
    reload: load,
  }
}
