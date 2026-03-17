declare const __API_BASE__: string

const API_BASE = __API_BASE__ || '/api'
const AUTH_HINT_KEY = 'auth_session'
const CSRF_COOKIE_NAME = 'creatorhub_csrf'

export type BootstrapStatus = {
  admin_username: string
  needs_password_setup: boolean
}

export type AuthSession = {
  id: string
  created_at: string
  last_activity_at: string
  expires_at: string
  idle_expires_at: string
  ip_address: string | null
  device_label: string | null
  user_agent: string | null
  mfa_verified: boolean
  is_current: boolean
}

export type LoginHistoryEntry = {
  id: string
  username: string | null
  occurred_at: string
  ip_address: string | null
  user_agent: string | null
  success: boolean
  suspicious: boolean
  reason: string | null
}

export type UserSummary = {
  id: string
  username: string
  role: 'admin' | 'editor' | 'viewer'
  is_active: boolean
  needs_password_setup: boolean
  mfa_enabled: boolean
  active_sessions: number
}

export type RegistrationRequest = {
  id: string
  username: string
  status: 'pending' | 'approved' | 'rejected'
}

export function getToken(): string | null {
  return localStorage.getItem(AUTH_HINT_KEY)
}

export function setToken(t: string | null) {
  if (t) localStorage.setItem(AUTH_HINT_KEY, '1')
  else localStorage.removeItem(AUTH_HINT_KEY)
}

function getCookie(name: string): string | null {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

function isUnsafeMethod(method?: string): boolean {
  const m = (method || 'GET').toUpperCase()
  return m === 'POST' || m === 'PUT' || m === 'PATCH' || m === 'DELETE'
}

export async function login(username: string, password: string, otp?: string): Promise<void> {
  const body = new URLSearchParams()
  body.set('username', username)
  body.set('password', password)
  if (otp?.trim()) body.set('otp', otp.trim())

  const res = await fetch(`${API_BASE}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
    credentials: 'include'
  })
  if (!res.ok) throw new Error(await res.text())
  setToken('1')
}

export async function refreshSession(): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    credentials: 'include'
  })
  if (!res.ok) throw new Error(await res.text())
  setToken('1')
}

export async function getBootstrapStatus(bootstrapToken: string): Promise<BootstrapStatus> {
  const res = await fetch(`${API_BASE}/auth/bootstrap-status`, {
    credentials: 'include',
    headers: { 'X-Bootstrap-Token': bootstrapToken }
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function setupAdminPassword(password: string, bootstrapToken: string): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/setup-admin-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Bootstrap-Token': bootstrapToken },
    body: JSON.stringify({ password }),
    credentials: 'include'
  })
  if (!res.ok) throw new Error(await res.text())
  setToken('1')
}

export async function requestRegistration(username: string, password: string): Promise<RegistrationRequest> {
  const res = await fetch(`${API_BASE}/auth/register-request`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
    credentials: 'include'
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function logout(): Promise<void> {
  try {
    await apiFetch('/auth/logout', { method: 'POST' })
  } finally {
    setToken(null)
  }
}

export async function checkSession(): Promise<boolean> {
  try {
    await apiFetch('/auth/me')
    setToken('1')
    return true
  } catch {
    setToken(null)
    return false
  }
}

export async function apiFetch(path: string, options: RequestInit = {}) {
  return apiFetchInternal(path, options, true)
}

async function apiFetchInternal(path: string, options: RequestInit = {}, allowRefresh = true) {
  const headers = new Headers(options.headers || {})
  if (isUnsafeMethod(options.method)) {
    const csrf = getCookie(CSRF_COOKIE_NAME)
    if (csrf) headers.set('X-CSRF-Token', csrf)
  }
  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: 'include' })
  if (!res.ok) {
    if (res.status === 401 && allowRefresh && path !== '/auth/refresh' && path !== '/auth/token') {
      try {
        await refreshSession()
        return apiFetchInternal(path, options, false)
      } catch {
        setToken(null)
      }
    }
    if (res.status === 401) {
      setToken(null)
    }
    const txt = await res.text()
    throw new Error(txt || res.statusText)
  }
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json()
  return res.text()
}


export async function apiFetchBlob(path: string): Promise<Blob> {
  const headers = new Headers()
  const res = await fetch(`${API_BASE}${path}`, { headers, credentials: 'include' })
  if (!res.ok) {
    if (res.status === 401) {
      setToken(null)
    }
    throw new Error(await res.text())
  }
  return res.blob()
}

export async function getMySessions(): Promise<AuthSession[]> {
  return apiFetch('/auth/sessions')
}

export async function revokeSession(sessionId: string): Promise<void> {
  await apiFetch(`/auth/sessions/${sessionId}`, { method: 'DELETE' })
}

export async function getLoginHistory(limit = 30): Promise<LoginHistoryEntry[]> {
  return apiFetch(`/auth/login-history?limit=${limit}`)
}

export async function getUsers(): Promise<UserSummary[]> {
  return apiFetch('/auth/users')
}

export async function getMfaStatus(): Promise<{ enabled: boolean }> {
  return apiFetch('/auth/mfa/status')
}

export async function provisionMfa(): Promise<{ secret: string; otpauth_uri: string }> {
  return apiFetch('/auth/mfa/provision', { method: 'POST' })
}

export async function enableMfa(secret: string, code: string): Promise<{ recovery_codes: string[] }> {
  return apiFetch('/auth/mfa/enable', { method: 'POST', body: JSON.stringify({ secret, code }) })
}

export async function disableMfa(password: string, code: string): Promise<{ enabled: boolean }> {
  return apiFetch('/auth/mfa/disable', { method: 'POST', body: JSON.stringify({ password, code }) })
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await apiFetch('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
  })
}

export async function requestPasswordReset(username: string): Promise<{ ok: boolean; reset_token: string | null }> {
  return apiFetch('/auth/password-reset/request', { method: 'POST', body: JSON.stringify({ username }) })
}

export async function confirmPasswordReset(token: string, newPassword: string): Promise<void> {
  await apiFetch('/auth/password-reset/confirm', {
    method: 'POST',
    body: JSON.stringify({ token, new_password: newPassword })
  })
}
