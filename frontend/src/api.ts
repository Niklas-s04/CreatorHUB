declare const __API_BASE__: string

const API_BASE = __API_BASE__ || '/api'
const AUTH_HINT_KEY = 'auth_session'
const CSRF_COOKIE_NAME = 'creatorhub_csrf'

export type BootstrapStatus = {
  admin_username: string
  needs_password_setup: boolean
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

export async function login(username: string, password: string): Promise<void> {
  const body = new URLSearchParams()
  body.set('username', username)
  body.set('password', password)

  const res = await fetch(`${API_BASE}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
    credentials: 'include'
  })
  if (!res.ok) throw new Error(await res.text())
  setToken('1')
}

export async function getBootstrapStatus(): Promise<BootstrapStatus> {
  const res = await fetch(`${API_BASE}/auth/bootstrap-status`, { credentials: 'include' })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function setupAdminPassword(password: string): Promise<void> {
  const res = await fetch(`${API_BASE}/auth/setup-admin-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
