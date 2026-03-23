import { createHttpClient } from './shared/api/httpClient'

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
  permissions: Permission[]
}

export type Permission =
  | 'product.read'
  | 'product.write'
  | 'product.delete'
  | 'product.import'
  | 'product.export'
  | 'product.auto_archive'
  | 'asset.read'
  | 'asset.upload'
  | 'asset.review'
  | 'content.read'
  | 'content.manage'
  | 'deal.read'
  | 'deal.manage'
  | 'email.read'
  | 'email.generate'
  | 'image.search'
  | 'knowledge.read'
  | 'knowledge.manage'
  | 'user.read'
  | 'user.manage'
  | 'user.approve_registration'
  | 'audit.view'

export type Me = {
  id: string
  username: string
  role: 'admin' | 'editor' | 'viewer'
  is_active: boolean
  needs_password_setup: boolean
  permissions: Permission[]
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

export type ApiRequestOptions = RequestInit & {
  timeoutMs?: number
  retries?: number
  retryDelayMs?: number
  shouldRetry?: (status: number) => boolean
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

const httpClient = createHttpClient({
  baseUrl: API_BASE,
  refreshPath: '/auth/refresh',
  tokenPath: '/auth/token',
  onUnauthorized: () => setToken(null),
  onUnauthorizedRetry: async () => {
    await refreshSession()
  },
  beforeRequest: (headers, options) => {
    if (isUnsafeMethod(options.method)) {
      const csrf = getCookie(CSRF_COOKIE_NAME)
      if (csrf) headers.set('X-CSRF-Token', csrf)
    }
  },
})

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

export async function getMe(): Promise<Me> {
  return apiFetch('/auth/me')
}

export async function apiFetch<T = unknown>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  return httpClient.request<T>(path, options)
}


export async function apiFetchBlob(path: string, options: ApiRequestOptions = {}): Promise<Blob> {
  return httpClient.requestBlob(path, options)
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
