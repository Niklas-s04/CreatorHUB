import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  apiFetch,
  apiFetchBlob,
  apiUrl,
  approveRegistrationRequest,
  changePassword,
  checkSession,
  confirmPasswordReset,
  deleteAccount,
  disableMfa,
  enableMfa,
  getBootstrapStatus,
  getLoginHistory,
  getMe,
  getMfaStatus,
  getMySessions,
  getRegistrationRequests,
  getToken,
  getUserSessions,
  getUsers,
  lockUser,
  login,
  logout,
  performMfaStepUp,
  provisionMfa,
  rejectRegistrationRequest,
  requestAdminPasswordReset,
  requestPasswordReset,
  requestRegistration,
  revokeSession,
  setStepUpHandler,
  setToken,
  setupAdminPassword,
  unlockUser,
} from './api'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

function textResponse(body: string, status = 200) {
  return new Response(body, { status })
}

describe('apiFetch step-up retry flow', () => {
  beforeEach(() => {
    setStepUpHandler(null)
    vi.stubGlobal('fetch', vi.fn())
    localStorage.clear()
    document.cookie = 'creatorhub_csrf=; Max-Age=0'
  })

  afterEach(() => {
    vi.useRealTimers()
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

    await expect(
      apiFetch('/sensitive', { method: 'POST', body: JSON.stringify({ value: 1 }) })
    ).resolves.toEqual({
      ok: true,
    })

    expect(stepUp).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/sensitive')
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/sensitive')
  })

  it('manages the local auth hint and builds API URLs', () => {
    expect(apiUrl('/health')).toBe('/api/v1/health')
    expect(getToken()).toBeNull()

    setToken('1')
    expect(getToken()).toBe('1')

    setToken(null)
    expect(getToken()).toBeNull()
  })

  it('submits login and bootstrap auth requests', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ account_deletion_canceled: true }))
      .mockResolvedValueOnce(jsonResponse({ admin_username: 'admin', needs_password_setup: true }))
      .mockResolvedValueOnce(textResponse('ok'))
      .mockResolvedValueOnce(
        jsonResponse({ id: 'request-1', username: 'new-user', status: 'pending' })
      )

    await expect(login('admin', 'secret', ' 123456 ')).resolves.toEqual({
      account_deletion_canceled: true,
    })
    await expect(getBootstrapStatus('bootstrap-token')).resolves.toEqual({
      admin_username: 'admin',
      needs_password_setup: true,
    })
    await setupAdminPassword('new-password', 'bootstrap-token')
    await expect(requestRegistration('new-user', 'secret')).resolves.toMatchObject({
      id: 'request-1',
    })

    const loginBody = fetchMock.mock.calls[0]?.[1]?.body
    expect(loginBody).toBeInstanceOf(URLSearchParams)
    expect((loginBody as URLSearchParams).get('otp')).toBe('123456')
    expect(fetchMock.mock.calls[1]?.[1]?.headers).toEqual({
      'X-Bootstrap-Token': 'bootstrap-token',
    })
    expect(getToken()).toBe('1')
  })

  it('throws response text for failed direct auth requests', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockResolvedValueOnce(textResponse('invalid credentials', 401))

    await expect(login('admin', 'wrong')).rejects.toThrow('invalid credentials')
    expect(getToken()).toBeNull()
  })

  it('preserves the response status for failed bootstrap checks', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(textResponse('temporarily unavailable', 503))

    await expect(getBootstrapStatus('bootstrap-token')).rejects.toMatchObject({
      name: 'ApiError',
      status: 503,
      message: 'temporarily unavailable',
    })
  })

  it('keeps normal auth timeouts short and allows longer admin setup requests', async () => {
    vi.useFakeTimers()
    const fetchMock = vi.mocked(fetch)
    const neverRespond = (_input: RequestInfo | URL, init?: RequestInit) => {
      const signal = init?.signal
      return new Promise<Response>((_resolve, reject) => {
        signal?.addEventListener('abort', () => {
          reject(new DOMException('Aborted', 'AbortError'))
        })
      })
    }
    fetchMock.mockImplementation(neverRespond)

    const loginRequest = login('admin', 'password')
    const loginAssertion = expect(loginRequest).rejects.toThrow('Anfrage hat zu lange gedauert')
    await vi.advanceTimersByTimeAsync(12_000)
    await loginAssertion

    const request = setupAdminPassword('new-password', 'bootstrap-token')
    const assertion = expect(request).rejects.toThrow('Anfrage hat zu lange gedauert')
    await vi.advanceTimersByTimeAsync(59_999)
    const setupStillPending = Promise.race([
      request.then(() => 'resolved'),
      Promise.resolve('pending'),
    ])
    await expect(setupStillPending).resolves.toBe('pending')
    await vi.advanceTimersByTimeAsync(1)

    await assertion
    vi.useRealTimers()
  })

  it('adds CSRF headers to unsafe apiFetch requests and supports blobs', async () => {
    const fetchMock = vi.mocked(fetch)
    document.cookie = 'creatorhub_csrf=csrf-token'
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ ok: true }))
      .mockResolvedValueOnce(new Response('file-content', { status: 200 }))

    await expect(
      apiFetch('/write', { method: 'POST', body: JSON.stringify({ ok: true }) })
    ).resolves.toEqual({
      ok: true,
    })
    await expect(apiFetchBlob('/export')).resolves.toMatchObject({ size: 12 })

    const headers = fetchMock.mock.calls[0]?.[1]?.headers as Headers
    expect(headers.get('X-CSRF-Token')).toBe('csrf-token')
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/v1/export')
  })

  it('updates the auth hint for session checks and cleanup flows', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ id: 'me' }))
      .mockResolvedValueOnce(textResponse('unauthorized', 401))
      .mockResolvedValueOnce(textResponse('refresh failed', 401))
      .mockResolvedValueOnce(textResponse('logout failed', 500))
      .mockResolvedValueOnce(jsonResponse({ ok: 'true', message: 'deleted' }))

    await expect(checkSession()).resolves.toBe(true)
    expect(getToken()).toBe('1')

    await expect(checkSession()).resolves.toBe(false)
    expect(getToken()).toBeNull()

    setToken('1')
    await expect(logout()).rejects.toThrow('logout failed')
    expect(getToken()).toBeNull()

    setToken('1')
    await expect(deleteAccount()).resolves.toEqual({ ok: 'true', message: 'deleted' })
    expect(getToken()).toBeNull()
  })

  it('treats forbidden sessions as anonymous', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockResolvedValueOnce(textResponse('forbidden', 403))
    setToken('1')

    await expect(checkSession()).resolves.toBe(false)

    expect(getToken()).toBeNull()
  })

  it('preserves the auth hint and propagates server or network failures', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockImplementation(async () => textResponse('server unavailable', 500))
    setToken('1')

    await expect(checkSession()).rejects.toThrow('server unavailable')
    expect(getToken()).toBe('1')

    fetchMock.mockReset()
    fetchMock.mockRejectedValueOnce(new Error('network unavailable'))

    await expect(checkSession()).rejects.toThrow('network unavailable')
    expect(getToken()).toBe('1')
  })

  it('maps auth and admin helper functions to their API endpoints', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock.mockImplementation(() => Promise.resolve(jsonResponse({ ok: true })))

    await getRegistrationRequests()
    await getRegistrationRequests('pending')
    await approveRegistrationRequest('request-1')
    await rejectRegistrationRequest('request-1', 'missing info')
    await getMe()
    await getMySessions()
    await revokeSession('session-1')
    await getLoginHistory(12)
    await getUsers()
    await getUserSessions('user-1')
    await requestAdminPasswordReset('user-1')
    await lockUser('user-1')
    await lockUser('user-1', 15)
    await unlockUser('user-1')
    await getMfaStatus()
    await performMfaStepUp('123456')
    await provisionMfa()
    await enableMfa('secret', '123456')
    await disableMfa('password', '123456')
    await changePassword('old-password', 'new-password')
    await requestPasswordReset('admin')
    await confirmPasswordReset('token', 'new-password')

    const calls = fetchMock.mock.calls.map((call) => [call[0], call[1]?.method ?? 'GET'])
    expect(calls).toContainEqual(['/api/v1/auth/registration-requests', 'GET'])
    expect(calls).toContainEqual([
      '/api/v1/auth/registration-requests?status_filter=pending',
      'GET',
    ])
    expect(calls).toContainEqual(['/api/v1/auth/registration-requests/request-1/approve', 'POST'])
    expect(calls).toContainEqual([
      '/api/v1/auth/registration-requests/request-1/reject?reason=missing%20info',
      'POST',
    ])
    expect(calls).toContainEqual(['/api/v1/auth/users/user-1/lock?minutes=15', 'POST'])
    expect(calls).toContainEqual(['/api/v1/auth/mfa/step-up', 'POST'])
    expect(calls).toContainEqual(['/api/v1/auth/password-reset/confirm', 'POST'])
  })
})
