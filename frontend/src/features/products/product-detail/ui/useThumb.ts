import { useEffect, useState } from 'react'
import { apiFetchBlob } from '../../../../api'

export function useThumb(assetId: string | null) {
  const [url, setUrl] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    let obj: string | null = null

    ;(async () => {
      if (!assetId) {
        setUrl(null)
        return
      }
      try {
        const blob = await apiFetchBlob(`/assets/${assetId}/thumb`)
        obj = URL.createObjectURL(blob)
        if (active) setUrl(obj)
      } catch {
        if (active) setUrl(null)
      }
    })()

    return () => {
      active = false
      if (obj) URL.revokeObjectURL(obj)
    }
  }, [assetId])

  return url
}
