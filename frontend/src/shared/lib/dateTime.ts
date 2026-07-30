type DateValue = Date | string | null | undefined

const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/
const GERMAN_TIME_ZONE = 'Europe/Berlin'

function parseDateOnly(value: string): Date | null {
  const match = DATE_ONLY_PATTERN.exec(value)
  if (!match) return null

  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const date = new Date(Date.UTC(year, month - 1, day, 12))

  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    return null
  }

  return date
}

function parseDateValue(value: DateValue): Date | null {
  if (!value) return null
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value

  const dateOnly = parseDateOnly(value)
  if (dateOnly) return dateOnly

  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatGermanDate(value: DateValue, fallback = '—'): string {
  const date = parseDateValue(value)
  if (!date) return fallback

  return new Intl.DateTimeFormat('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: GERMAN_TIME_ZONE,
  }).format(date)
}

export function formatGermanDateTime(value: DateValue, fallback = '—'): string {
  if (typeof value === 'string' && DATE_ONLY_PATTERN.test(value)) {
    const formattedDate = formatGermanDate(value, fallback)
    return formattedDate === fallback ? fallback : `${formattedDate}, 00:00`
  }

  const date = parseDateValue(value)
  if (!date) return fallback

  return new Intl.DateTimeFormat('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone: GERMAN_TIME_ZONE,
  }).format(date)
}
