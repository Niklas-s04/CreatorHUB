import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, createHttpClient } from './httpClient'

function createClient(overrides: Partial<Parameters<typeof createHttpClient>[0]> = {}) {
  return createHttpClient({
    baseUrl: '/api/v1',
    refreshPath: '/auth/refresh',
    tokenPath: '/auth/token',
    ...overrides,
  })
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

function textResponse(body: string, status = 200) {
  return new Response(body, { status })
}

describe('createHttpClient', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
    vi.spyOn(Math, 'random').mockReturnValue(0)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('returns JSON and applies request defaults', async () => {
    const beforeRequest = vi.fn((headers: Headers) => {
      headers.set('X-Test', 'yes')
    })
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockResolvedValueOnce(jsonResponse({ ok: true }))

    await expect(createClient({ beforeRequest }).request('/items')).resolves.toEqual({ ok: true })

    const request = fetchMock.mock.calls[0]?.[1]
    const headers = request?.headers as Headers
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/items')
    expect(request?.credentials).toBe('include')
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('X-Test')).toBe('yes')
    expect(request).not.toHaveProperty('timeoutMs')
    expect(request).not.toHaveProperty('retries')
    expect(request).not.toHaveProperty('retryDelayMs')
    expect(request).not.toHaveProperty('shouldRetry')
  })

  it('returns text responses without JSON parsing', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockResolvedValueOnce(textResponse('plain text'))

    await expect(createClient().request('/text')).resolves.toBe('plain text')
  })

  it('refreshes once after unauthorized responses', async () => {
    const onUnauthorizedRetry = vi.fn().mockResolvedValue(undefined)
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(textResponse('expired', 401))
      .mockResolvedValueOnce(jsonResponse({ ok: true }))

    await expect(createClient({ onUnauthorizedRetry }).request('/profile')).resolves.toEqual({
      ok: true,
    })

    expect(onUnauthorizedRetry).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('clears auth state when refresh retry fails', async () => {
    const onUnauthorized = vi.fn()
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockResolvedValueOnce(textResponse('expired', 401))

    await expect(
      createClient({
        onUnauthorized,
        onUnauthorizedRetry: vi.fn().mockRejectedValue(new Error('refresh failed')),
      }).request('/profile')
    ).rejects.toMatchObject({ status: 401, details: 'expired' })

    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('retries idempotent network failures', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockRejectedValueOnce(new TypeError('network'))
      .mockResolvedValueOnce(jsonResponse({ ok: true }))

    await expect(createClient().request('/retry', { retryDelayMs: 0 })).resolves.toEqual({
      ok: true,
    })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('throws API errors for non-retryable failed responses', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockResolvedValueOnce(textResponse('bad request', 400))

    const error = await createClient()
      .request('/bad')
      .catch((err) => err)

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({
      status: 400,
      path: '/bad',
      details: 'bad request',
    })
  })

  it('supports blob responses and reports blob request failures', async () => {
    const onUnauthorized = vi.fn()
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(new Response('content', { status: 200 }))
      .mockResolvedValueOnce(textResponse('no access', 401))

    await expect(createClient().requestBlob('/file')).resolves.toMatchObject({ size: 7 })
    await expect(createClient({ onUnauthorized }).requestBlob('/file')).rejects.toMatchObject({
      status: 401,
      details: 'no access',
    })
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('refreshes once before retrying unauthorized blob responses', async () => {
    const onUnauthorizedRetry = vi.fn().mockResolvedValue(undefined)
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(textResponse('expired', 401))
      .mockResolvedValueOnce(new Response('file-content', { status: 200 }))

    await expect(createClient({ onUnauthorizedRetry }).requestBlob('/file')).resolves.toMatchObject(
      { size: 12 }
    )

    expect(onUnauthorizedRetry).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('shares one refresh across parallel unauthorized requests', async () => {
    let resolveRefresh: (() => void) | undefined
    const refreshPending = new Promise<void>((resolve) => {
      resolveRefresh = resolve
    })
    const onUnauthorizedRetry = vi.fn(() => refreshPending)
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(textResponse('expired', 401))
      .mockResolvedValueOnce(textResponse('expired', 401))
      .mockResolvedValueOnce(jsonResponse({ id: 1 }))
      .mockResolvedValueOnce(jsonResponse({ id: 2 }))

    const client = createClient({ onUnauthorizedRetry })
    const first = client.request('/first')
    const second = client.request('/second')
    await vi.waitFor(() => expect(onUnauthorizedRetry).toHaveBeenCalledTimes(1))
    resolveRefresh?.()

    await expect(Promise.all([first, second])).resolves.toEqual([{ id: 1 }, { id: 2 }])
    expect(onUnauthorizedRetry).toHaveBeenCalledTimes(1)
  })

  it('honors a caller abort signal without retrying', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockImplementation(
      (_input, init) =>
        new Promise((_resolve, reject) => {
          init?.signal?.addEventListener(
            'abort',
            () => reject(new DOMException('Aborted', 'AbortError')),
            { once: true }
          )
        })
    )
    const controller = new AbortController()
    const result = createClient().request('/slow', {
      signal: controller.signal,
      retries: 2,
    })
    controller.abort()

    await expect(result).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
