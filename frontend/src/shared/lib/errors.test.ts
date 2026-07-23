import { describe, expect, it } from 'vitest'
import { getErrorKind, getErrorMessage, getValidationFieldErrors } from './errors'

describe('errors', () => {
  it('parses the documented API error envelope and validation details', () => {
    const error = new Error(
      JSON.stringify({
        code: 'VALIDATION_ERROR',
        message: 'Request validation failed',
        status: 422,
        details: [{ loc: ['body', 'name'], msg: 'required' }],
      })
    )

    expect(getErrorMessage(error)).toBe('required')
    expect(getValidationFieldErrors(error)).toEqual({ name: 'required' })
    expect(getErrorKind(error)).toBe('domain')
  })

  it('uses the envelope message when structured details are empty', () => {
    const error = {
      code: 'NOT_FOUND',
      message: 'Project not found',
      status: 404,
      details: null,
    }

    expect(getErrorMessage(error)).toBe('Project not found')
    expect(getValidationFieldErrors(error)).toEqual({})
    expect(getErrorKind(error)).toBe('domain')
  })

  it('keeps legacy detail responses as a fallback', () => {
    expect(getErrorMessage(new Error(JSON.stringify({ detail: 'kaputt' })))).toBe('kaputt')
    expect(getErrorMessage({ detail: 'missing' })).toBe('missing')
    expect(
      getValidationFieldErrors({ detail: [{ loc: ['body', 'name'], msg: 'required' }] })
    ).toEqual({ name: 'required' })
    expect(getErrorKind({ detail: [] })).toBe('domain')
  })

  it('classifies standardized server failures as technical errors', () => {
    const error = {
      code: 'SERVICE_UNAVAILABLE',
      message: 'Service temporarily unavailable',
      status: 503,
      details: null,
    }

    expect(getErrorMessage(error)).toBe('Service temporarily unavailable')
    expect(getErrorKind(error)).toBe('technical')
  })

  it('unwraps incomplete creator profile API errors for email UI alerts', () => {
    const detail =
      'Creator AI profile is incomplete. Configure clear name, artist name, channel link, themes and platforms. Missing: clear_name'

    expect(
      getErrorMessage(
        new Error(
          JSON.stringify({
            code: 'BAD_REQUEST',
            message: detail,
            status: 400,
            details: null,
          })
        )
      )
    ).toBe(detail)
  })
})
