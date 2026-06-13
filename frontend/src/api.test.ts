import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiFetch, setStepUpHandler } from './api'

describe('apiFetch step-up retry flow', () => {
  beforeEach(() => {
    setStepUpHandler(null)
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    setStepUpHandler(null)
    vi.unstubAllGlobals()
  })

  it('prompts for step-up and retries the original request once', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Step-up authentication required' }), {
          status: 403,
          headers: { 'content-type': 'application/json' },
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        })
      )

    const stepUp = vi.fn().mockResolvedValue(undefined)
    setStepUpHandler(stepUp)

    await expect(apiFetch('/sensitive', { method: 'POST', body: JSON.stringify({ value: 1 }) })).resolves.toEqual({
      ok: true,
    })

    expect(stepUp).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/sensitive')
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/sensitive')
  })
})
