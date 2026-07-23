import { act, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ImageSearchJobDto } from '../../../../shared/api/contracts'
import { useImageSearchJobPolling } from './useImageSearchJobPolling'

function result(status: ImageSearchJobDto['status']): ImageSearchJobDto {
  return {
    status,
    result: status === 'finished' ? { query: 'camera', count: 1, candidates: [{}] } : null,
    error: status === 'failed' ? 'search failed' : null,
  }
}

afterEach(() => {
  vi.useRealTimers()
})

describe('useImageSearchJobPolling', () => {
  it.each(['finished', 'failed'] as const)('stops polling after %s', async (status) => {
    vi.useFakeTimers()
    const poll = vi.fn().mockResolvedValue(result(status))
    const onStatus = vi.fn()
    const onFinished = vi.fn()
    const onFailed = vi.fn()

    renderHook(() =>
      useImageSearchJobPolling({
        jobId: 'job-1',
        poll,
        onStatus,
        onFinished,
        onFailed,
        onError: vi.fn(),
        intervalMs: 100,
      })
    )

    await act(async () => {
      await Promise.resolve()
    })
    await act(async () => {
      vi.advanceTimersByTime(500)
      await Promise.resolve()
    })

    expect(poll).toHaveBeenCalledTimes(1)
    expect(onStatus).toHaveBeenCalledWith(status)
    expect(status === 'finished' ? onFinished : onFailed).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('ignores a pending response after unmount and creates no follow-up timer', async () => {
    vi.useFakeTimers()
    let resolvePoll: ((value: ImageSearchJobDto) => void) | undefined
    const poll = vi.fn(
      () =>
        new Promise<ImageSearchJobDto>((resolve) => {
          resolvePoll = resolve
        })
    )
    const onStatus = vi.fn()
    const onFinished = vi.fn()
    const onFailed = vi.fn()
    const onError = vi.fn()

    const { unmount } = renderHook(() =>
      useImageSearchJobPolling({
        jobId: 'job-1',
        poll,
        onStatus,
        onFinished,
        onFailed,
        onError,
        intervalMs: 100,
      })
    )

    expect(poll).toHaveBeenCalledTimes(1)
    unmount()

    await act(async () => {
      resolvePoll?.(result('running'))
      await Promise.resolve()
    })

    expect(onStatus).not.toHaveBeenCalled()
    expect(onFinished).not.toHaveBeenCalled()
    expect(onFailed).not.toHaveBeenCalled()
    expect(onError).not.toHaveBeenCalled()
    expect(vi.getTimerCount()).toBe(0)
  })
})
