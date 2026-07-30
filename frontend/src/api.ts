import { ApiError, createHttpClient } from './shared/api/httpClient'

declare const __API_BASE__: string

export const API_BASE = __API_BASE__ || '/api/v1'
const AUTH_HINT_KEY = 'auth_session'
export const ACTION_CONFIRMATION_HEADERS = {
  'X-Action-Confirm': 'CONFIRM',
} as const
const CSRF_COOKIE_NAME = 'creatorhub_csrf'
const AUTH_REQUEST_TIMEOUT_MS = 12_000
const ADMIN_SETUP_TIMEOUT_MS = 60_000

export type BootstrapStatus = {
  admin_username: string
  needs_password_setup: boolean
}

export type LoginResult = {
  account_deletion_canceled: boolean
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
  mfa_step_up_expires_at: string | null
  is_current: boolean
}

export type AdminSession = AuthSession & {
  revoked_at: string | null
  revoked_reason: string | null
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
  locked_until: string | null
  last_activity_at: string | null
  active_sessions: number
  permissions: Permission[]
}

export type CreateUserInput = {
  username: string
  password: string
  role: 'editor' | 'viewer'
  is_active: boolean
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
  | 'project.read'
  | 'project.manage'
  | 'project.delete'
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
  reviewed_at: string | null
  reviewed_by_user_id: string | null
  reviewed_by_username: string | null
  rejection_reason: string | null
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

type StepUpHandler = () => Promise<void>
let stepUpHandler: StepUpHandler | null = null

export function setStepUpHandler(handler: StepUpHandler | null) {
  stepUpHandler = handler
}

function isStepUpRequiredError(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false
  if (error.status !== 403) return false
  return (
    error.details.includes('Step-up authentication required') ||
    error.message.includes('Step-up authentication required')
  )
}

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`
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

function isAbortError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'name' in error &&
    (error as { name?: unknown }).name === 'AbortError'
  )
}

type AuthFetchOptions = RequestInit & {
  timeoutMs?: number
}

async function authFetch(path: string, options: AuthFetchOptions = {}): Promise<Response> {
  const { timeoutMs = AUTH_REQUEST_TIMEOUT_MS, ...requestOptions } = options
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(`${API_BASE}${path}`, {
      ...requestOptions,
      signal: controller.signal,
      credentials: 'include',
    })
  } catch (error: unknown) {
    if (isAbortError(error)) {
      throw new Error('Anfrage hat zu lange gedauert. Bitte Netzwerk oder Backend prüfen.')
    }
    throw error
  } finally {
    window.clearTimeout(timeout)
  }
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

export async function login(
  username: string,
  password: string,
  otp?: string
): Promise<LoginResult> {
  const body = new URLSearchParams()
  body.set('username', username)
  body.set('password', password)
  if (otp?.trim()) body.set('otp', otp.trim())

  const res = await authFetch('/auth/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  if (!res.ok) throw new Error(await res.text())

  let accountDeletionCanceled = false
  if ((res.headers.get('content-type') || '').includes('application/json')) {
    const payload = (await res.json()) as { account_deletion_canceled?: unknown }
    accountDeletionCanceled = payload.account_deletion_canceled === true
  }

  setToken('1')
  return { account_deletion_canceled: accountDeletionCanceled }
}

export async function refreshSession(): Promise<void> {
  const res = await authFetch('/auth/refresh', {
    method: 'POST',
  })
  if (!res.ok) throw new Error(await res.text())
  setToken('1')
}

export async function getBootstrapStatus(bootstrapToken: string): Promise<BootstrapStatus> {
  const path = '/auth/bootstrap-status'
  const res = await authFetch('/auth/bootstrap-status', {
    headers: { 'X-Bootstrap-Token': bootstrapToken },
  })
  if (!res.ok) {
    const details = await res.text()
    throw new ApiError(details || res.statusText, res.status, path, details)
  }
  return res.json()
}

export async function setupAdminPassword(password: string, bootstrapToken: string): Promise<void> {
  const res = await authFetch('/auth/setup-admin-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Bootstrap-Token': bootstrapToken },
    body: JSON.stringify({ password }),
    timeoutMs: ADMIN_SETUP_TIMEOUT_MS,
  })
  if (!res.ok) throw new Error(await res.text())
  setToken('1')
}

export async function requestRegistration(
  username: string,
  password: string
): Promise<RegistrationRequest> {
  const res = await authFetch('/auth/register-request', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function getRegistrationRequests(
  statusFilter?: 'pending' | 'approved' | 'rejected'
): Promise<RegistrationRequest[]> {
  const query = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : ''
  return apiFetch(`/auth/registration-requests${query}`)
}

export async function approveRegistrationRequest(requestId: string): Promise<RegistrationRequest> {
  return apiFetch(`/auth/registration-requests/${requestId}/approve`, { method: 'POST' })
}

export async function rejectRegistrationRequest(
  requestId: string,
  reason: string
): Promise<RegistrationRequest> {
  return apiFetch(
    `/auth/registration-requests/${requestId}/reject?reason=${encodeURIComponent(reason)}`,
    { method: 'POST' }
  )
}

export async function logout(): Promise<void> {
  try {
    await apiFetch('/auth/logout', { method: 'POST' })
  } finally {
    setToken(null)
  }
}

export async function deleteAccount(): Promise<{ ok: string; message: string }> {
  try {
    return await apiFetch('/auth/account', { method: 'DELETE' })
  } finally {
    setToken(null)
  }
}

export async function checkSession(): Promise<boolean> {
  try {
    await apiFetch('/auth/me')
    setToken('1')
    return true
  } catch (error: unknown) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
      setToken(null)
      return false
    }
    throw error
  }
}

export async function getMe(): Promise<Me> {
  return apiFetch('/auth/me')
}

export async function apiFetch<T = unknown>(
  path: string,
  options: ApiRequestOptions = {}
): Promise<T> {
  try {
    return await httpClient.request<T>(path, options)
  } catch (error: unknown) {
    if (path !== '/auth/mfa/step-up' && stepUpHandler && isStepUpRequiredError(error)) {
      await stepUpHandler()
      return httpClient.request<T>(path, options)
    }
    throw error
  }
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

export async function createUser(input: CreateUserInput): Promise<UserSummary> {
  return apiFetch('/auth/users', {
    method: 'POST',
    body: JSON.stringify(input),
  })
}

export async function getUserSessions(userId: string): Promise<AdminSession[]> {
  return apiFetch(`/auth/users/${userId}/sessions`)
}

export async function requestAdminPasswordReset(
  userId: string
): Promise<{ ok: boolean; reset_token: string | null }> {
  return apiFetch(`/auth/users/${userId}/password-reset`, { method: 'POST' })
}

export async function lockUser(userId: string, minutes?: number): Promise<UserSummary> {
  const query = typeof minutes === 'number' ? `?minutes=${encodeURIComponent(String(minutes))}` : ''
  return apiFetch(`/auth/users/${userId}/lock${query}`, { method: 'POST' })
}

export async function unlockUser(userId: string): Promise<UserSummary> {
  return apiFetch(`/auth/users/${userId}/unlock`, { method: 'POST' })
}

export async function getMfaStatus(): Promise<{ enabled: boolean }> {
  return apiFetch('/auth/mfa/status')
}

export async function performMfaStepUp(
  code: string
): Promise<{ mfa_verified: boolean; step_up_expires_at: string }> {
  return apiFetch('/auth/mfa/step-up', { method: 'POST', body: JSON.stringify({ code }) })
}

export async function provisionMfa(): Promise<{ secret: string; otpauth_uri: string }> {
  return apiFetch('/auth/mfa/provision', { method: 'POST' })
}

export async function enableMfa(
  secret: string,
  code: string
): Promise<{ recovery_codes: string[] }> {
  return apiFetch('/auth/mfa/enable', { method: 'POST', body: JSON.stringify({ secret, code }) })
}

export async function disableMfa(password: string, code: string): Promise<{ enabled: boolean }> {
  return apiFetch('/auth/mfa/disable', { method: 'POST', body: JSON.stringify({ password, code }) })
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  await apiFetch('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  })
}

export async function requestPasswordReset(
  username: string
): Promise<{ ok: boolean; reset_token: null }> {
  return apiFetch('/auth/password-reset/request', {
    method: 'POST',
    body: JSON.stringify({ username }),
  })
}

export async function confirmPasswordReset(token: string, newPassword: string): Promise<void> {
  await apiFetch('/auth/password-reset/confirm', {
    method: 'POST',
    body: JSON.stringify({ token, new_password: newPassword }),
  })
}
