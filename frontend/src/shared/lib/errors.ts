type ValidationFieldErrors = Record<string, string>
export type ErrorKind = 'domain' | 'technical'

function safeJsonParse(input: string): unknown {
  try {
    return JSON.parse(input)
  } catch {
    return null
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function getDetails(source: Record<string, unknown>): unknown {
  if (source.details !== undefined) return source.details
  return source.detail
}

function normalizeDetail(detail: unknown): string | null {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (!Array.isArray(detail)) return null
  const messages = detail
    .map((item) => {
      if (typeof item === 'string') return item
      if (isRecord(item) && typeof item.msg === 'string') return item.msg
      return ''
    })
    .filter(Boolean)
  return messages.length ? messages.join(' · ') : null
}

function unwrapError(error: unknown): unknown {
  if (!(error instanceof Error)) return error
  const parsed = safeJsonParse(error.message)
  return parsed ?? error
}

export function getErrorMessage(error: unknown): string {
  const source = unwrapError(error)
  if (typeof source === 'string' && source.trim()) return source

  if (isRecord(source)) {
    const detailMessage = normalizeDetail(getDetails(source))
    if (detailMessage) return detailMessage
    if (typeof source.message === 'string' && source.message.trim()) return source.message
  }

  if (error instanceof Error && error.message.trim()) return error.message
  return 'Unbekannter Fehler'
}

export function getValidationFieldErrors(error: unknown): ValidationFieldErrors {
  const source = unwrapError(error)
  if (!isRecord(source)) return {}
  const details = getDetails(source)
  if (!Array.isArray(details)) return {}

  const result: ValidationFieldErrors = {}
  details.forEach((item) => {
    if (!isRecord(item)) return
    const loc = Array.isArray(item.loc) ? item.loc : []
    const msg = typeof item.msg === 'string' ? item.msg : null
    if (!msg) return

    const field = loc
      .filter((segment) => typeof segment === 'string' && segment !== 'body')
      .join('.')

    if (field) {
      result[field] = msg
    }
  })

  return result
}

export function getErrorKind(error: unknown): ErrorKind {
  const fieldErrors = getValidationFieldErrors(error)
  if (Object.keys(fieldErrors).length > 0) return 'domain'

  const source = unwrapError(error)
  if (isRecord(source)) {
    if (typeof source.status === 'number') {
      return source.status >= 400 && source.status < 500 ? 'domain' : 'technical'
    }
    if (source.details !== undefined || source.detail !== undefined) return 'domain'
  }
  return 'technical'
}
