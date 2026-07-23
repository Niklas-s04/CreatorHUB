import { useEffect, useRef } from 'react'
import type { ImageSearchJobDto } from '../../../../shared/api/contracts'

type ImageSearchJobPollingOptions = {
  jobId: string | null
  poll: (jobId: string) => Promise<ImageSearchJobDto>
  onStatus: (status: ImageSearchJobDto['status']) => void
  onFinished: (result: ImageSearchJobDto['result']) => void
  onFailed: (error: string | null) => void
  onError: (error: unknown) => void
  intervalMs?: number
}

export function useImageSearchJobPolling({
  jobId,
  poll,
  onStatus,
  onFinished,
  onFailed,
  onError,
  intervalMs = 1200,
}: ImageSearchJobPollingOptions) {
  const handlersRef = useRef({ poll, onStatus, onFinished, onFailed, onError })

  useEffect(() => {
    handlersRef.current = { poll, onStatus, onFinished, onFailed, onError }
  }, [poll, onStatus, onFinished, onFailed, onError])

  useEffect(() => {
    if (!jobId) return

    let active = true
    let timer: ReturnType<typeof setTimeout> | null = null

    const tick = async () => {
      try {
        const result = await handlersRef.current.poll(jobId)
        if (!active) return

        handlersRef.current.onStatus(result.status)

        if (result.status === 'finished') {
          handlersRef.current.onFinished(result.result)
          return
        }

        if (result.status === 'failed') {
          handlersRef.current.onFailed(result.error)
          return
        }

        timer = setTimeout(() => {
          void tick()
        }, intervalMs)
      } catch (error: unknown) {
        if (active) handlersRef.current.onError(error)
      }
    }

    void tick()

    return () => {
      active = false
      if (timer) clearTimeout(timer)
    }
  }, [intervalMs, jobId])
}
