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
  return new Promise((resolve) => setTimeout(resolve, ms))
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

function toError(error: unknown): Error {
  if (error instanceof Error) return error
  if (typeof error === 'object' && error !== null) {
    const candidate = error as { name?: unknown; message?: unknown }
    const normalized = new Error(
      typeof candidate.message === 'string' ? candidate.message : String(error)
    )
    if (typeof candidate.name === 'string') normalized.name = candidate.name
    return normalized
  }
  return new Error(String(error))
}

function createAttemptController(callerSignal: AbortSignal | null | undefined, timeoutMs: number) {
  const controller = new AbortController()
  let timedOut = false
  const abortFromCaller = () => controller.abort(callerSignal?.reason)
  if (callerSignal?.aborted) {
    abortFromCaller()
  } else {
    callerSignal?.addEventListener('abort', abortFromCaller, { once: true })
  }
  const timeout = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  return {
    signal: controller.signal,
    didTimeOut: () => timedOut,
    cleanup: () => {
      clearTimeout(timeout)
      callerSignal?.removeEventListener('abort', abortFromCaller)
    },
  }
}

export function createHttpClient(context: HttpClientContext) {
  let refreshPromise: Promise<void> | null = null

  async function refreshOnce(): Promise<void> {
    if (!context.onUnauthorizedRetry) return
    if (!refreshPromise) {
      refreshPromise = context.onUnauthorizedRetry().finally(() => {
        refreshPromise = null
      })
    }
    await refreshPromise
  }

  async function request<T = unknown>(
    path: string,
    options: JsonRequestOptions = {},
    allowRefresh = true
  ): Promise<T> {
    const method = (options.method || 'GET').toUpperCase()
    const timeoutMs = options.timeoutMs ?? 12_000
    const retries = options.retries ?? (isIdempotent(method) ? 2 : 0)
    const retryDelayMs = options.retryDelayMs ?? 250
    const shouldRetry = options.shouldRetry ?? defaultShouldRetry
    const {
      timeoutMs: _timeoutMs,
      retries: _retries,
      retryDelayMs: _retryDelayMs,
      shouldRetry: _shouldRetry,
      ...requestOptions
    } = options

    let lastError: Error | null = null

    for (let attempt = 0; attempt <= retries; attempt += 1) {
      const attemptController = createAttemptController(options.signal, timeoutMs)

      try {
        const headers = new Headers(options.headers || {})
        if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
          headers.set('Content-Type', 'application/json')
        }

        context.beforeRequest?.(headers, options)

        const res = await fetch(`${context.baseUrl}${path}`, {
          ...requestOptions,
          headers,
          signal: attemptController.signal,
          credentials: 'include',
        })

        if (!res.ok) {
          if (
            res.status === 401 &&
            allowRefresh &&
            path !== context.refreshPath &&
            path !== context.tokenPath &&
            context.onUnauthorizedRetry
          ) {
            try {
              await refreshOnce()
              return request<T>(path, options, false)
            } catch {
              // Continue with the original unauthorized response below.
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
        const err = toError(error)
        lastError = err

        const isAbortError = err.name === 'AbortError'
        const canRetry =
          attempt < retries &&
          !options.signal?.aborted &&
          ((isAbortError && attemptController.didTimeOut()) || err instanceof TypeError)

        if (!canRetry) {
          throw err
        }

        await delay(backoff(attempt + 1, retryDelayMs))
      } finally {
        attemptController.cleanup()
      }
    }

    throw lastError ?? new Error('Unbekannter Netzwerkfehler')
  }

  async function requestBlob(
    path: string,
    options: JsonRequestOptions = {},
    allowRefresh = true
  ): Promise<Blob> {
    const method = (options.method || 'GET').toUpperCase()
    const timeoutMs = options.timeoutMs ?? 12_000
    const retries = options.retries ?? (isIdempotent(method) ? 1 : 0)
    const retryDelayMs = options.retryDelayMs ?? 250
    const shouldRetry = options.shouldRetry ?? defaultShouldRetry
    const {
      timeoutMs: _timeoutMs,
      retries: _retries,
      retryDelayMs: _retryDelayMs,
      shouldRetry: _shouldRetry,
      ...requestOptions
    } = options

    let lastError: Error | null = null

    for (let attempt = 0; attempt <= retries; attempt += 1) {
      const attemptController = createAttemptController(options.signal, timeoutMs)

      try {
        const headers = new Headers(options.headers || {})
        context.beforeRequest?.(headers, options)

        const res = await fetch(`${context.baseUrl}${path}`, {
          ...requestOptions,
          headers,
          signal: attemptController.signal,
          credentials: 'include',
        })

        if (!res.ok) {
          if (
            res.status === 401 &&
            allowRefresh &&
            path !== context.refreshPath &&
            path !== context.tokenPath &&
            context.onUnauthorizedRetry
          ) {
            try {
              await refreshOnce()
              return requestBlob(path, options, false)
            } catch {
              // Continue with the original unauthorized response below.
            }
          }

          if (res.status === 401) context.onUnauthorized?.()
          const text = await res.text()
          const err = new ApiError(text || res.statusText, res.status, path, text)
          if (attempt < retries && shouldRetry(res.status)) {
            await delay(backoff(attempt + 1, retryDelayMs))
            continue
          }
          throw err
        }

        return await res.blob()
      } catch (error: unknown) {
        const err = toError(error)
        lastError = err
        const canRetry =
          attempt < retries &&
          !options.signal?.aborted &&
          ((err.name === 'AbortError' && attemptController.didTimeOut()) ||
            err instanceof TypeError)
        if (!canRetry) throw err
        await delay(backoff(attempt + 1, retryDelayMs))
      } finally {
        attemptController.cleanup()
      }
    }

    throw lastError ?? new Error('Blob-Request fehlgeschlagen')
  }

  return {
    request,
    requestBlob,
  }
}
