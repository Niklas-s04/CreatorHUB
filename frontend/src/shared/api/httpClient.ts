export class ApiError extends Error {
  status: number
  path: string
  details: string

  constructor(message: string, status: number, path: string, details: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.path = path
    this.details = details
  }
}

type HttpClientOptions = {
  method?: string
  timeoutMs?: number
  retries?: number
  retryDelayMs?: number
  shouldRetry?: (status: number) => boolean
}

type JsonRequestOptions = RequestInit & HttpClientOptions

type HttpClientContext = {
  baseUrl: string
  refreshPath: string
  tokenPath: string
  authHeaderName?: string
  onUnauthorized?: () => void
  beforeRequest?: (headers: Headers, options: JsonRequestOptions) => void
  onUnauthorizedRetry?: () => Promise<void>
}

function delay(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function isIdempotent(method?: string) {
  const m = (method || 'GET').toUpperCase()
  return m === 'GET' || m === 'HEAD' || m === 'OPTIONS'
}

function defaultShouldRetry(status: number) {
  return status === 408 || status === 425 || status === 429 || status >= 500
}

function backoff(attempt: number, baseDelay: number) {
  const jitter = Math.floor(Math.random() * 120)
  return baseDelay * 2 ** (attempt - 1) + jitter
}

export function createHttpClient(context: HttpClientContext) {
  async function request<T = unknown>(path: string, options: JsonRequestOptions = {}, allowRefresh = true): Promise<T> {
    const method = (options.method || 'GET').toUpperCase()
    const timeoutMs = options.timeoutMs ?? 12_000
    const retries = options.retries ?? (isIdempotent(method) ? 2 : 0)
    const retryDelayMs = options.retryDelayMs ?? 250
    const shouldRetry = options.shouldRetry ?? defaultShouldRetry

    let lastError: Error | null = null

    for (let attempt = 0; attempt <= retries; attempt += 1) {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), timeoutMs)

      try {
        const headers = new Headers(options.headers || {})
        if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
          headers.set('Content-Type', 'application/json')
        }

        context.beforeRequest?.(headers, options)

        const res = await fetch(`${context.baseUrl}${path}`, {
          ...options,
          headers,
          signal: controller.signal,
          credentials: 'include',
        })

        if (!res.ok) {
          if (res.status === 401 && allowRefresh && path !== context.refreshPath && path !== context.tokenPath && context.onUnauthorizedRetry) {
            try {
              await context.onUnauthorizedRetry()
              return request<T>(path, options, false)
            } catch {
              context.onUnauthorized?.()
            }
          }

          if (res.status === 401) {
            context.onUnauthorized?.()
          }

          const text = await res.text()
          const err = new ApiError(text || res.statusText, res.status, path, text)

          if (attempt < retries && shouldRetry(res.status)) {
            await delay(backoff(attempt + 1, retryDelayMs))
            continue
          }

          throw err
        }

        const contentType = res.headers.get('content-type') || ''
        if (contentType.includes('application/json')) {
          return (await res.json()) as T
        }

        return (await res.text()) as T
      } catch (error: unknown) {
        const err = error instanceof Error ? error : new Error(String(error))
        lastError = err

        const isAbortError = err.name === 'AbortError'
        const canRetry = attempt < retries && (isAbortError || err instanceof TypeError)

        if (!canRetry) {
          throw err
        }

        await delay(backoff(attempt + 1, retryDelayMs))
      } finally {
        clearTimeout(timeout)
      }
    }

    throw lastError ?? new Error('Unbekannter Netzwerkfehler')
  }

  async function requestBlob(path: string, options: JsonRequestOptions = {}): Promise<Blob> {
    const method = (options.method || 'GET').toUpperCase()
    const timeoutMs = options.timeoutMs ?? 12_000
    const retries = options.retries ?? (isIdempotent(method) ? 1 : 0)

    let lastError: Error | null = null

    for (let attempt = 0; attempt <= retries; attempt += 1) {
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), timeoutMs)

      try {
        const headers = new Headers(options.headers || {})
        context.beforeRequest?.(headers, options)

        const res = await fetch(`${context.baseUrl}${path}`, {
          ...options,
          headers,
          signal: controller.signal,
          credentials: 'include',
        })

        if (!res.ok) {
          if (res.status === 401) context.onUnauthorized?.()
          const text = await res.text()
          throw new ApiError(text || res.statusText, res.status, path, text)
        }

        return await res.blob()
      } catch (error: unknown) {
        const err = error instanceof Error ? error : new Error(String(error))
        lastError = err
        const canRetry = attempt < retries && (err.name === 'AbortError' || err instanceof TypeError)
        if (!canRetry) throw err
      } finally {
        clearTimeout(timeout)
      }
    }

    throw lastError ?? new Error('Blob-Request fehlgeschlagen')
  }

  return {
    request,
    requestBlob,
  }
}
