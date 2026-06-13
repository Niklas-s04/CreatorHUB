import { describe, expect, it } from 'vitest'
import { getErrorKind, getErrorMessage, getValidationFieldErrors } from './errors'

describe('errors', () => {
  it('unwraps json error messages and validation details', () => {
    expect(getErrorMessage(new Error(JSON.stringify({ detail: 'kaputt' })))).toBe('kaputt')
    expect(getErrorMessage({ detail: 'missing' })).toBe('missing')
    expect(getValidationFieldErrors({ detail: [{ loc: ['body', 'name'], msg: 'required' }] })).toEqual({ name: 'required' })
    expect(getErrorKind({ detail: [] })).toBe('domain')
  })
})