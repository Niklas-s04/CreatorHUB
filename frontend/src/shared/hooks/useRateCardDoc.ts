import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../api'
import { getErrorMessage } from '../lib/errors'

export type RateCardDoc = {
  id: string
  title: string
  content: string
}

export function useRateCardDoc() {
  const [doc, setDoc] = useState<RateCardDoc | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const list = await apiFetch<RateCardDoc[]>('/knowledge?type=rate_card')
      setDoc(list[0] || null)
      setError(null)
    } catch (e: unknown) {
      setError(getErrorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return { doc, loading, error, reload: load }
}
