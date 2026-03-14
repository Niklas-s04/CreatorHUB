import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../api'

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
      const list = await apiFetch('/knowledge?type=rate_card') as RateCardDoc[]
      setDoc(list[0] || null)
      setError(null)
    } catch (e: any) {
      setError(e.message || String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return { doc, loading, error, reload: load }
}
