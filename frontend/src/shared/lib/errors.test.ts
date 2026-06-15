import { describe, expect, it } from 'vitest'
import { getErrorKind, getErrorMessage, getValidationFieldErrors } from './errors'

describe('errors', () => {
  it('unwraps json error messages and validation details', () => {
    expect(getErrorMessage(new Error(JSON.stringify({ detail: 'kaputt' })))).toBe('kaputt')
    expect(getErrorMessage({ detail: 'missing' })).toBe('missing')
    expect(
      getValidationFieldErrors({ detail: [{ loc: ['body', 'name'], msg: 'required' }] })
    ).toEqual({ name: 'required' })
    expect(getErrorKind({ detail: [] })).toBe('domain')
  })

  it('unwraps incomplete creator profile API errors for email UI alerts', () => {
    const detail =
      'Creator AI profile is incomplete. Configure clear name, artist name, channel link, themes and platforms. Missing: clear_name'

    expect(getErrorMessage(new Error(JSON.stringify({ detail })))).toBe(detail)
  })
})
