import { describe, expect, it } from 'vitest'
import { formatGermanDate, formatGermanDateTime } from './dateTime'

describe('German date and time formatting', () => {
  it('formats date-only values without a timezone shift', () => {
    expect(formatGermanDate('2026-01-02')).toBe('02.01.2026')
  })

  it('formats timestamps in the German timezone and 24-hour clock', () => {
    expect(formatGermanDateTime('2026-07-31T12:05:00Z')).toBe('31.07.2026, 14:05')
    expect(formatGermanDateTime('2026-07-31')).toBe('31.07.2026, 00:00')
  })

  it('uses the requested fallback for missing or invalid values', () => {
    expect(formatGermanDate(null)).toBe('—')
    expect(formatGermanDateTime('not-a-date', '-')).toBe('-')
  })
})
